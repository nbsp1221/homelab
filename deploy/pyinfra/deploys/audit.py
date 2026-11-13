from pyinfra.operations import server

from homelab_infra.dns import DNS_READY

server.shell(
    name="Report host baseline",
    commands=r"""
set -eu
. /etc/os-release
printf 'os=%s %s\n' "$ID" "$VERSION_ID"
printf 'kernel=%s\n' "$(uname -r)"
printf 'architecture=%s\n' "$(uname -m)"
printf 'memory_kib=%s\n' "$(awk '/MemTotal:/ { print $2 }' /proc/meminfo)"
active_swap=$(/sbin/swapon --show=NAME --noheadings --raw | paste -sd, -)
docker_version=$(docker version --format '{{.Server.Version}}' 2>/dev/null || true)
printf 'active_swap=%s\n' "$active_swap"
printf 'docker_version=%s\n' "$docker_version"
printf 'compose_version=%s\n' "$(docker compose version --short 2>/dev/null || true)"
printf 'docker_service=%s\n' "$(systemctl is-active docker 2>/dev/null || true)"
printf 'resolver_link=%s\n' "$(readlink -f /etc/resolv.conf 2>/dev/null || true)"
resolver_service=$(systemctl is-active systemd-resolved 2>/dev/null || true)
printf 'resolver_service=%s\n' "$resolver_service"
printf 'tailscale_service=%s\n' "$(systemctl is-active tailscaled 2>/dev/null || true)"
if test -e /var/run/reboot-required; then
  printf 'reboot_required=yes\n'
else
  printf 'reboot_required=no\n'
fi
""",
)

server.shell(
    name="Report resolver integration without activating a service",
    commands=(
        f"if {DNS_READY}; then echo dns_integration=resolved; "
        "else echo dns_integration=other; fi"
    ),
)
