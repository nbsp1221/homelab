from collections.abc import Iterable
from dataclasses import dataclass

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.deb import DebPackages
from pyinfra.facts.server import Arch, Command, LinuxDistribution
from pyinfra.operations import apt, server, systemd

from homelab_infra.package_state import packages_need_upgrade

DOCKER_PACKAGES = (
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    "docker-buildx-plugin",
    "docker-compose-plugin",
)
DOCKER_CONFLICTING_PACKAGES = frozenset(
    {
        "containerd",
        "docker.io",
        "docker-compose",
        "docker-compose-v2",
        "podman-docker",
        "runc",
    }
)


@dataclass(frozen=True, slots=True)
class DockerRepository:
    uri: str
    key_uri: str
    suite: str
    architecture: str


def docker_repository(
    distribution: str,
    release: str,
    architecture: str,
) -> DockerRepository:
    distribution_slug = distribution.lower()
    if distribution_slug not in {"debian", "ubuntu"}:
        raise ValueError("Docker automation supports Debian and Ubuntu only")

    architecture_slug = {
        "x86_64": "amd64",
        "aarch64": "arm64",
    }.get(architecture, architecture)
    uri = f"https://download.docker.com/linux/{distribution_slug}"
    return DockerRepository(
        uri=uri,
        key_uri=f"{uri}/gpg",
        suite=release,
        architecture=architecture_slug,
    )


def installed_conflicts(installed_packages: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(DOCKER_CONFLICTING_PACKAGES & set(installed_packages)))


@deploy("Configure Docker Engine")
def configure_docker() -> None:
    installed_packages = host.get_fact(DebPackages)
    conflicts = installed_conflicts(installed_packages)
    if conflicts:
        raise DeployError(
            "Conflicting Docker packages are installed: " + ", ".join(conflicts)
        )

    distribution = host.get_fact(LinuxDistribution)
    name = distribution["name"]
    release_meta = distribution["release_meta"]
    release = release_meta.get("VERSION_CODENAME") or release_meta.get(
        "UBUNTU_CODENAME"
    )
    architecture = host.get_fact(Arch)
    if not name or not release or not architecture:
        raise DeployError("Could not determine distribution, release, or architecture")

    try:
        repository = docker_repository(name, release, architecture)
    except ValueError as error:
        raise DeployError(str(error)) from error

    key_result = apt.key(
        name="Install Docker's APT signing key",
        src=repository.key_uri,
        dest="docker.gpg",
    )
    repository_result = apt.sources_file(
        name="Configure Docker's official APT repository",
        filename="docker",
        uris=[repository.uri],
        suites=[repository.suite],
        components=["stable"],
        architectures=[repository.architecture],
        signed_by="/etc/apt/keyrings/docker.gpg",
    )

    if key_result.will_change or repository_result.will_change:
        apt.update(name="Refresh Docker repository metadata", cache_time=0)

    upgradable_packages = host.get_fact(
        Command,
        command="apt list --upgradable 2>/dev/null || true",
    )
    held_packages = host.get_fact(
        Command,
        command="apt-mark showhold 2>/dev/null || true",
    )
    apt.packages(
        name="Install current Docker Engine and Compose",
        packages=list(DOCKER_PACKAGES),
        present=True,
        latest=packages_need_upgrade(
            upgradable_packages,
            held_packages,
            DOCKER_PACKAGES,
        ),
        update=True,
        cache_time=3600,
    )
    systemd.service(
        name="Enable and start Docker Engine",
        service="docker",
        running=True,
        enabled=True,
    )

    for operator in host.data.docker_users:
        server.user(
            name=f"Grant {operator} access to Docker Engine",
            user=operator,
            groups=["docker"],
            append=True,
        )
