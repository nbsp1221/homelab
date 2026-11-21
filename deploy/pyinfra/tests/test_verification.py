import os
import shlex
import subprocess

import pytest

from homelab_infra.verification import build_baseline_verification


@pytest.mark.parametrize(
    "failure",
    [
        "",
        "swap-size",
        "swap-mode",
        "swap-owner",
        "fstab",
        "swap-inactive",
        "repository",
        "docker-version",
        "docker-inactive",
        "docker-disabled",
        "compose",
        "operator-group",
    ],
)
def test_baseline_verification_requires_every_runtime_prerequisite(
    tmp_path, failure
) -> None:
    swap = tmp_path / "example-swap"
    swap.write_bytes(bytes(0 if failure == "swap-size" else 1024 * 1024))
    swap.chmod(0o644 if failure == "swap-mode" else 0o600)
    fstab = tmp_path / "fstab"
    fstab.write_text("" if failure == "fstab" else f"{swap} none swap sw 0 0\n")
    sources = tmp_path / "docker.sources"
    sources.write_text(
        "URIs: https://packages.example/\n"
        if failure == "repository"
        else "URIs: https://download.docker.com/linux/debian\n"
    )
    tools = tmp_path / "bin"
    tools.mkdir()
    scripts = {
        "stat": """\
if [ "$2" = "%U:%G" ]; then
    if [ "$FAILURE" = swap-owner ]; then echo operator:operator
    else echo root:root; fi
else
    command -p stat "$@"
fi
""",
        "swapon": 'if [ "$FAILURE" != swap-inactive ]; then echo "$SWAP"; fi\n',
        "dpkg-query": "echo 2\n",
        "apt-cache": """\
test "$LC_ALL" = C || exit 99
if [ "$FAILURE" = docker-version ]; then echo 'Candidate: 3'
else echo 'Candidate: 2'; fi
""",
        "systemctl": """\
case "$1" in
    is-active) test "$FAILURE" != docker-inactive ;;
    is-enabled) test "$FAILURE" != docker-disabled ;;
    *) exit 99 ;;
esac
""",
        "docker": """\
case "$1" in
    version) echo server=2 ;;
    compose) test "$FAILURE" != compose ;;
    *) exit 99 ;;
esac
""",
        "id": """\
test "$#" -eq 3 && test "$3" = 'test operator' || exit 99
if [ "$FAILURE" = operator-group ]; then echo users
else echo 'users docker'; fi
""",
    }
    for name, script in scripts.items():
        command = tools / name
        command.write_text("#!/bin/sh\n" + script)
        command.chmod(0o700)

    script = build_baseline_verification(str(swap), 1, ("test operator",))
    script = script.replace("/etc/fstab", shlex.quote(str(fstab)))
    script = script.replace(
        "/etc/apt/sources.list.d/docker.sources", shlex.quote(str(sources))
    )
    result = subprocess.run(
        ["/bin/sh", "-c", script],
        env={
            **os.environ,
            "PATH": f"{tools}:{os.environ['PATH']}",
            "FAILURE": failure,
            "SWAP": str(swap),
        },
        text=True,
        capture_output=True,
        timeout=5,
    )
    assert (result.returncode == 0) is (not failure), result.stderr
