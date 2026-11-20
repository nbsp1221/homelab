import os
import shlex
import subprocess

import pytest

from homelab_infra.monitoring import build_monitoring_verification


@pytest.fixture
def monitoring_stacks():
    return {
        "caddy-gcp": {
            "env": {
                "CADDY_DOMAIN": "monitor.example",
                "CADDY_BIND_IPV4": "192.0.2.20",
                "CADDY_BIND_IPV6": "2001:db8::20",
            }
        },
        "beszel-hub": {},
    }


@pytest.mark.parametrize("missing", ["caddy-gcp", "beszel-hub"])
def test_checks_require_both_proxy_and_hub(monitoring_stacks, missing) -> None:
    del monitoring_stacks[missing]
    assert build_monitoring_verification({"stacks": monitoring_stacks}) == ""


@pytest.mark.parametrize(
    "failed_probe",
    ["", "-4:healthz", "-6:healthz", "-4:proxy", "-4:health", "-6:health"],
)
def test_checks_require_valid_responses_on_both_address_families(
    tmp_path, monitoring_stacks, failed_probe
) -> None:
    tools = tmp_path / "bin"
    tools.mkdir()
    curl = tools / "curl"
    curl.write_text(
        """\
#!/bin/sh
printf '%s\n' "$*" >> "$LOG"
family=
url=
for arg do
    case "$arg" in
        -4|-6) family=$arg ;;
        https://*) url=$arg ;;
    esac
done
case "$url" in
    https://*/healthz)
        if [ "$FAILURE" = "$family:healthz" ]; then exit 60; fi
        if [ "$FAILURE" = "$family:proxy" ]; then echo wrong-proxy
        else echo gcp-caddy-ok; fi ;;
    https://*/api/health)
        if [ "$FAILURE" = "$family:health" ]; then echo '{"code":500}'
        else echo '{"code":200}'; fi ;;
    *) exit 99 ;;
esac
"""
    )
    curl.chmod(0o700)
    getent = tools / "getent"
    getent.write_text("#!/bin/sh\nexit 0\n")
    getent.chmod(0o700)
    log = tmp_path / "requests"
    script = build_monitoring_verification({"stacks": monitoring_stacks})
    result = subprocess.run(
        ["/bin/sh", "-ec", script],
        env={
            **os.environ,
            "PATH": f"{tools}:{os.environ['PATH']}",
            "FAILURE": failed_probe,
            "LOG": str(log),
        },
        text=True,
        capture_output=True,
    )
    assert (result.returncode == 0) is (not failed_probe), result.stderr
    if not failed_probe:
        requests = [shlex.split(line) for line in log.read_text().splitlines()]
        assert {
            (
                next(flag for flag in ("-4", "-6") if flag in args),
                args[args.index("--resolve") + 1],
                next(arg for arg in args if arg.startswith("https://")),
            )
            for args in requests
        } == {
            (
                family,
                f"monitor.example:443:{address}",
                f"https://monitor.example/{path}",
            )
            for family, address in (("-4", "192.0.2.20"), ("-6", "[2001:db8::20]"))
            for path in ("healthz", "api/health")
        }
        assert all(not {"--insecure", "-k"}.intersection(args) for args in requests)
