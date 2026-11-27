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
        docker.DebPackages: {},
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
    assert download.call_args.kwargs["force"] is True
    for operation in packages.call_args_list:
        assert operation.kwargs["extra_install_args"] == "--no-remove"
        assert not operation.kwargs.get("latest")
    prerequisites, install = [operation.kwargs for operation in packages.call_args_list]
    assert set(prerequisites["packages"]) == {"ca-certificates", "curl"}
    assert "docker-compose-plugin" in install["packages"]
    assert install["update"] is True


def test_install_rejects_distribution_compose_before_any_apt_operation(monkeypatch):
    facts = {
        docker.LinuxDistribution: {
            "name": "Ubuntu",
            "release_meta": {"UBUNTU_CODENAME": "noble"},
        },
        docker.DebArch: "amd64",
        docker.DebPackages: {"docker-compose-v2": ["2.40.3"]},
    }
    monkeypatch.setattr(
        docker, "host", SimpleNamespace(data={}, get_fact=facts.__getitem__)
    )
    packages, download = Mock(), Mock()
    monkeypatch.setattr(docker.apt, "packages", packages)
    monkeypatch.setattr(docker.files, "download", download)

    with pytest.raises(docker.DeployError, match="manual removal: docker-compose-v2"):
        docker.install._inner()

    packages.assert_not_called()
    download.assert_not_called()


@pytest.mark.parametrize("missing_compose", [False, True])
def test_reapply_downloads_the_key_only_when_needed(monkeypatch, missing_compose):
    installed = {
        package: ["1"]
        for package in (*docker.DOCKER_PACKAGES, *docker.DOCKER_PREREQUISITES)
    }
    if missing_compose:
        del installed["docker-compose-plugin"]
    facts = {
        docker.LinuxDistribution: {
            "name": "Ubuntu",
            "release_meta": {"UBUNTU_CODENAME": "resolute"},
        },
        docker.DebArch: "amd64",
        docker.DebPackages: installed,
    }
    monkeypatch.setattr(
        docker, "host", SimpleNamespace(data={}, get_fact=facts.__getitem__)
    )
    packages, download = Mock(), Mock()
    monkeypatch.setattr(docker.apt, "packages", packages)
    monkeypatch.setattr(docker.apt, "sources_file", Mock())
    monkeypatch.setattr(docker.files, "directory", Mock())
    monkeypatch.setattr(docker.files, "download", download)
    monkeypatch.setattr(docker.systemd, "service", Mock())

    docker.install._inner()

    assert packages.call_count == 1
    assert download.call_args.kwargs["force"] is missing_compose
