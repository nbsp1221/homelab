import os
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks import docker


def test_upgrade_targets_installed_unheld_packages(tmp_path):
    scripts = {
        "apt-mark": "echo docker-ce:amd64",
        "dpkg-query": 'case "$3" in docker-ce|docker-ce-cli) echo installed ;; esac',
        "apt-get": 'printf "%s\\n" "$@" > "$CAPTURE"',
    }
    for executable, body in scripts.items():
        shim = tmp_path / executable
        shim.write_text("#!/bin/sh\n" + body + "\n")
        shim.chmod(0o700)
    capture = tmp_path / "args"
    subprocess.run(
        ["sh", "-ec", docker.build_upgrade_command()],
        env={
            **os.environ,
            "PATH": f"{tmp_path}:{os.environ['PATH']}",
            "CAPTURE": str(capture),
        },
        check=True,
    )
    assert capture.read_text().splitlines() == [
        "install",
        "-y",
        "--only-upgrade",
        "--no-remove",
        "docker-ce-cli",
    ]


@pytest.mark.parametrize(
    ("distribution", "release_meta", "architecture", "suite"),
    [
        ("Debian", {"VERSION_CODENAME": "bookworm"}, "amd64", "bookworm"),
        (
            "Ubuntu",
            {"VERSION_CODENAME": "example", "UBUNTU_CODENAME": "noble"},
            "arm64",
            "noble",
        ),
    ],
)
def test_install_uses_the_official_apt_source_without_package_removals(
    monkeypatch, distribution, release_meta, architecture, suite
):
    facts = {
        docker.LinuxDistribution: {"name": distribution, "release_meta": release_meta},
        docker.DebArch: architecture,
    }
    monkeypatch.setattr(
        docker, "host", SimpleNamespace(data={}, get_fact=facts.__getitem__)
    )
    packages, source, download = Mock(), Mock(), Mock()
    monkeypatch.setattr(docker.apt, "packages", packages)
    monkeypatch.setattr(docker.apt, "sources_file", source)
    monkeypatch.setattr(docker.files, "directory", Mock())
    monkeypatch.setattr(docker.files, "download", download)
    monkeypatch.setattr(docker.systemd, "service", Mock())

    docker.install._inner()

    source_args = source.call_args.kwargs
    assert source_args["uris"] == [
        f"https://download.docker.com/linux/{distribution.lower()}"
    ]
    assert source_args["suites"] == [suite]
    assert source_args["architectures"] == [architecture]
    assert source_args["signed_by"] == download.call_args.kwargs["dest"]
    assert download.call_args.kwargs["src"] == f"{source_args['uris'][0]}/gpg"
    for operation in packages.call_args_list:
        assert operation.kwargs["extra_install_args"] == "--no-remove"
        assert not operation.kwargs.get("latest")
    prerequisites, install = [operation.kwargs for operation in packages.call_args_list]
    assert set(prerequisites["packages"]) == {"ca-certificates", "curl"}
    assert "docker-compose-plugin" in install["packages"]
    assert install["update"] is True
