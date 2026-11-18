import os
import subprocess

import pytest

from homelab_infra.hosts import load_hosts
from homelab_infra.monitoring import build_monitoring_verification


def test_only_the_declared_gcp_hub_gets_monitoring_checks() -> None:
    for name, definition in load_hosts().items():
        assert bool(build_monitoring_verification(definition)) == (
            name == "retn0-srv-gcp-01"
        )


@pytest.mark.parametrize("failure", ["", "tls", "proxy", "hub"])
def test_generated_checks_require_both_tls_listeners_and_the_real_hub(
    tmp_path, failure
) -> None:
    tools = tmp_path / "bin"
    tools.mkdir()
    curl = tools / "curl"
    curl.write_text(
        "#!/bin/sh\n"
        'echo "$*" >> "$LOG"\n'
        'test "$FAILURE" != tls || exit 60\n'
        'case "$*" in\n'
        '  */healthz) if test "$FAILURE" = proxy; then echo wrong; '
        "else echo gcp-caddy-ok; fi ;;\n"
        '  */api/health) if test "$FAILURE" = hub; then echo \'{"code":500}\'; '
        "else echo '{\"code\":200}'; fi ;;\nesac\n"
    )
    curl.chmod(0o700)
    getent = tools / "getent"
    getent.write_text("#!/bin/sh\nexit 0\n")
    getent.chmod(0o700)
    log = tmp_path / "requests"
    script = build_monitoring_verification(load_hosts()["retn0-srv-gcp-01"])
    result = subprocess.run(
        ["/bin/sh", "-ec", script],
        env={
            **os.environ,
            "PATH": f"{tools}:{os.environ['PATH']}",
            "FAILURE": failure,
            "LOG": str(log),
        },
        text=True,
        capture_output=True,
    )
    assert (result.returncode == 0) is (not failure)
    if not failure:
        requests = log.read_text().splitlines()
        assert len(requests) == 4
        assert "-4" in requests[0] and "100.82.114.104" in requests[0]
        assert "-6" in requests[2] and "[fd7a:115c:a1e0::7536:7269]" in requests[2]
        assert all("--resolve beszel.retn0.dev:443:" in r for r in requests)
        assert all("--insecure" not in r and " -k " not in r for r in requests)
