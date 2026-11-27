from shlex import join

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.deb import DebArch
from pyinfra.facts.server import LinuxDistribution, Users
from pyinfra.operations import apt, files, server, systemd

DOCKER_PACKAGES = (
    "docker-ce",
    "docker-ce-cli",
    "containerd.io",
    "docker-buildx-plugin",
    "docker-compose-plugin",
)
DOCKER_KEY_DIR = "/etc/apt/keyrings"
DOCKER_KEY_PATH = f"{DOCKER_KEY_DIR}/docker.asc"
APT_NO_REMOVE = "--no-remove"
APT_REFRESH = "apt-get -o APT::Update::Error-Mode=any update"


@deploy("Configure Docker Engine")
def install() -> None:
    distribution = host.get_fact(LinuxDistribution)
    name = (distribution["name"] or "").lower()
    if name not in {"debian", "ubuntu"}:
        raise DeployError("Docker automation supports Debian and Ubuntu only")

    release_meta = distribution["release_meta"]
    release = release_meta.get("VERSION_CODENAME")
    if name == "ubuntu":
        release = release_meta.get("UBUNTU_CODENAME") or release
    architecture = host.get_fact(DebArch)
    if not release or not architecture:
        raise DeployError(
            "Could not determine distribution release or APT architecture"
        )

    operators = tuple(host.data.get("docker_users", ()))
    if operators:
        missing = sorted(set(operators) - set(host.get_fact(Users)))
        if missing:
            raise DeployError(
                "Docker operators must already exist: " + ", ".join(missing)
            )

    repository = f"https://download.docker.com/linux/{name}"
    apt.packages(
        name="Install Docker repository prerequisites",
        packages=["ca-certificates", "curl"],
        update=True,
        cache_time=3600,
        extra_install_args=APT_NO_REMOVE,
    )
    files.directory(
        name="Create APT keyring directory",
        path=DOCKER_KEY_DIR,
        mode="0755",
    )
    files.download(
        name="Download Docker's APT signing key",
        src=f"{repository}/gpg",
        dest=DOCKER_KEY_PATH,
        mode="0644",
    )
    apt.sources_file(
        name="Configure Docker's official APT repository",
        filename="docker",
        uris=[repository],
        suites=[release],
        components=["stable"],
        architectures=[architecture],
        signed_by=DOCKER_KEY_PATH,
    )
    apt.packages(
        name="Install Docker Engine and Compose",
        packages=list(DOCKER_PACKAGES),
        update=True,
        extra_install_args=APT_NO_REMOVE,
    )
    systemd.service(
        name="Enable and start Docker Engine",
        service="docker",
        running=True,
        enabled=True,
    )

    for operator in operators:
        server.user(
            name=f"Grant {operator} access to Docker Engine",
            user=operator,
            groups=["docker"],
            append=True,
        )


def build_upgrade_command() -> str:
    packages = join(DOCKER_PACKAGES)
    return f"""\
set -eu
holds=$(apt-mark showhold)
status_format='${{db:Status-Status}}'
set --
for package in {packages}; do
    status=$(dpkg-query -W -f="$status_format" "$package" 2>/dev/null) || continue
    if [ "$status" != installed ]; then
        continue
    fi
    if printf '%s\\n' "$holds" | cut -d : -f 1 | grep -Fxq "$package"; then
        continue
    fi
    set -- "$@" "$package"
done
if [ "$#" -gt 0 ]; then
    export DEBIAN_FRONTEND=noninteractive
    apt-get install -y --only-upgrade {APT_NO_REMOVE} "$@"
fi
"""


@deploy("Upgrade installed Docker packages")
def upgrade() -> None:
    server.shell(
        name="Refresh APT metadata before upgrading Docker", commands=APT_REFRESH
    )
    server.shell(
        name="Upgrade installed, unheld Docker packages",
        commands=build_upgrade_command(),
    )
