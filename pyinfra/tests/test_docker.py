import pytest

from homelab_infra.docker import (
    DOCKER_PACKAGES,
    docker_repository,
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


def test_conflicting_packages_are_sorted_and_deduplicated() -> None:
    assert installed_conflicts(["runc", "curl", "docker.io", "runc"]) == (
        "docker.io",
        "runc",
    )
