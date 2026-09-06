from io import BytesIO

import pytest

from homelab_infra.docker import (
    DOCKER_KEY_PATH,
    DOCKER_PACKAGES,
    DOCKER_REPOSITORY_UPDATE_COMMAND,
    docker_repository,
    fetch_repository_key,
    installed_conflicts,
)


def test_docker_package_intent_is_explicit() -> None:
    assert DOCKER_PACKAGES == (
        "docker-ce",
        "docker-ce-cli",
        "containerd.io",
        "docker-buildx-plugin",
        "docker-compose-plugin",
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


def test_docker_repository_refresh_fails_on_any_apt_error() -> None:
    assert DOCKER_REPOSITORY_UPDATE_COMMAND == (
        "apt-get update -o APT::Update::Error-Mode=any"
    )


def test_repository_key_uses_docker_official_armored_format(monkeypatch) -> None:
    content = b"-----BEGIN PGP PUBLIC KEY BLOCK-----\nkey\n"
    requests: list[tuple[str, int]] = []

    def open_key(url: str, timeout: int) -> BytesIO:
        requests.append((url, timeout))
        return BytesIO(content)

    monkeypatch.setattr("homelab_infra.docker.urlopen", open_key)

    key_file = fetch_repository_key("https://download.docker.com/linux/debian/gpg")

    assert key_file.read() == content
    assert requests == [("https://download.docker.com/linux/debian/gpg", 30)]
    assert DOCKER_KEY_PATH == "/etc/apt/keyrings/docker.asc"


def test_repository_key_rejects_an_invalid_response(monkeypatch) -> None:
    monkeypatch.setattr(
        "homelab_infra.docker.urlopen",
        lambda _url, timeout: BytesIO(b"not a signing key"),
    )

    with pytest.raises(ValueError, match="ASCII-armored OpenPGP"):
        fetch_repository_key("https://download.docker.com/linux/debian/gpg")


def test_conflicting_packages_are_sorted_and_deduplicated() -> None:
    assert installed_conflicts(["runc", "curl", "docker.io", "runc"]) == (
        "docker.io",
        "runc",
    )
