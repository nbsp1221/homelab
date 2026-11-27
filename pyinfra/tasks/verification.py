import shlex
from textwrap import dedent

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import server

from tasks.dns import verify_dns
from tasks.swap import canonical_fstab_entry, swap_size_bytes, validate_path


def build_baseline_verification(
    swap_path: str,
    swap_size_mb: int,
    docker_users: tuple[str, ...],
) -> str:
    swap_path = validate_path(swap_path)
    expected_bytes = swap_size_bytes(swap_size_mb)
    fstab_entry = canonical_fstab_entry(swap_path)
    user_checks = "\n".join(
        f'id -nG -- {shlex.quote(user)} | tr " " "\\n" | grep -Fx docker'
        for user in docker_users
    )
    return dedent(
        f"""\
        set -eu
        test "$(stat -c %s "{swap_path}")" = "{expected_bytes}"
        test "$(stat -c %a "{swap_path}")" = 600
        test "$(stat -c %U:%G "{swap_path}")" = root:root
        test "$(grep -Fxc {shlex.quote(fstab_entry)} /etc/fstab)" = 1
        swapon --show=NAME --noheadings --raw | grep -Fx "{swap_path}"
        test -f /etc/apt/sources.list.d/docker.sources
        grep -F 'URIs: https://download.docker.com/linux/' \
          /etc/apt/sources.list.d/docker.sources
        test "$(dpkg-query -W -f='${{db:Status-Status}}' docker-ce)" = installed
        systemctl is-active --quiet docker
        systemctl is-enabled --quiet docker
        docker version --format 'server={{{{.Server.Version}}}}'
        docker compose version --short
        {user_checks}
        """
    )


@deploy("Verify host baseline")
def verify() -> None:
    server.shell(
        name="Verify the complete host baseline",
        commands=build_baseline_verification(
            host.data.swap_path,
            host.data.swap_size_mb,
            tuple(host.data.get("docker_users", ())),
        ),
    )
    verify_dns()
