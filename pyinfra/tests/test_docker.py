import os
import subprocess
from io import BytesIO

import pytest

from tasks.docker import (
    build_upgrade_command,
    docker_package_candidate_available,
    docker_repository,
    fetch_repository_key,
    installed_conflicts,
)


@pytest.mark.parametrize(
    ("distribution", "release", "architecture", "expected"),
    [
        (
            "Debian",
            "bookworm",
            "x86_64",
            (
                "https://download.docker.com/linux/debian",
                "https://download.docker.com/linux/debian/gpg",
                "bookworm",
                "amd64",
            ),
        ),
        (
            "Ubuntu",
            "noble",
            "aarch64",
            (
                "https://download.docker.com/linux/ubuntu",
                "https://download.docker.com/linux/ubuntu/gpg",
                "noble",
                "arm64",
            ),
        ),
    ],
)
def test_docker_repository_mapping(
    distribution: str,
    release: str,
    architecture: str,
    expected: tuple[str, str, str, str],
) -> None:
    repository = docker_repository(distribution, release, architecture)

    assert (
        repository.uri,
        repository.key_uri,
        repository.suite,
        repository.architecture,
    ) == expected


def test_docker_repository_rejects_unsupported_distribution() -> None:
    with pytest.raises(ValueError, match="Debian and Ubuntu"):
        docker_repository("Fedora", "42", "x86_64")


@pytest.mark.parametrize(
    ("policy", "expected"),
    [
        ("docker-ce:\n  Candidate: 5:29.0.0-1~debian.12~bookworm\n", True),
        ("docker-ce:\n  Candidate: (none)\n", False),
        ("", False),
    ],
)
def test_docker_package_candidate_availability(
    policy: str,
    expected: bool,
) -> None:
    assert docker_package_candidate_available(policy) is expected


def test_repository_key_uses_docker_official_armored_format(monkeypatch) -> None:
    content = b"-----BEGIN PGP PUBLIC KEY BLOCK-----\nkey\n"
    requests: list[str] = []

    def open_key(url: str, timeout: int) -> BytesIO:
        requests.append(url)
        return BytesIO(content)

    monkeypatch.setattr("tasks.docker.urlopen", open_key)

    key_file = fetch_repository_key("https://download.docker.com/linux/debian/gpg")

    assert key_file.read() == content
    assert requests == ["https://download.docker.com/linux/debian/gpg"]


def test_repository_key_rejects_an_invalid_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "tasks.docker.urlopen",
        lambda _url, timeout: BytesIO(b"not a signing key"),
    )

    with pytest.raises(ValueError, match="ASCII-armored OpenPGP"):
        fetch_repository_key("https://download.docker.com/linux/debian/gpg")


def test_conflicting_packages_are_sorted_and_deduplicated() -> None:
    assert installed_conflicts(["runc", "curl", "docker.io", "runc"]) == (
        "docker.io",
        "runc",
    )


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
        ["sh", "-ec", build_upgrade_command()],
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
        "docker-ce-cli",
    ]
