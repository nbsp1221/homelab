from io import StringIO
from ipaddress import ip_address

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.server import Command
from pyinfra.operations import files, systemd

from homelab_infra.hosts import load_hosts

DROP_IN_DIRECTORY = "/etc/systemd/system/docker.service.d"
DROP_IN_PATH = f"{DROP_IN_DIRECTORY}/10-homelab-tailscale.conf"
PREREQUISITES = (
    "test -x /usr/sbin/ip && test -x /usr/bin/grep && "
    "/usr/bin/tailscale wait --help >/dev/null 2>&1 && "
    "systemctl cat tailscaled.service >/dev/null 2>&1 && "
    "printf ready || true"
)


def tailscale_bind_addresses(definition: dict) -> tuple[str, ...]:
    caddy = definition["stacks"].get("caddy-gcp")
    if caddy is None:
        return ()
    environment = caddy.get("env", {})
    addresses = []
    for version in (4, 6):
        address = ip_address(environment.get(f"CADDY_BIND_IPV{version}", ""))
        if address.version != version or "%" in str(address):
            raise ValueError(f"Caddy requires an unscoped IPv{version} bind address")
        addresses.append(str(address))
    return tuple(addresses)


def render_docker_startup(addresses: tuple[str, ...]) -> str:
    lines = [
        "# Managed by homelab pyinfra; Docker publishes these host addresses.",
        "[Unit]",
        "Wants=tailscaled.service",
        "After=tailscaled.service",
        "StartLimitIntervalSec=0",
        "",
        "[Service]",
        "ExecStartPre=/usr/bin/tailscale wait --timeout=60s",
    ]
    # tailscale wait currently checks only the first assigned IP. Docker needs
    # both published addresses on the real interface, including usable IPv6.
    for value in addresses:
        address = ip_address(value)
        if "%" in str(address):
            raise ValueError("Scoped bind addresses are not supported")
        lines.append(
            "ExecStartPre=/bin/sh -ec '/usr/sbin/ip -o address show "
            f"dev tailscale0 to {address}/{address.max_prefixlen} "
            "-tentative -dadfailed | /usr/bin/grep -q .'"
        )
    lines.extend(["Restart=always", "RestartSec=10s", ""])
    return "\n".join(lines)


@deploy("Configure Docker startup dependencies")
def configure_docker_startup() -> None:
    addresses = tailscale_bind_addresses(load_hosts()[host.name])
    if addresses:
        if host.get_fact(Command, command=PREREQUISITES) != "ready":
            raise DeployError(
                "Docker startup requires tailscale wait, tailscaled.service, "
                "iproute2 and grep; install/enroll Tailscale separately"
            )
        files.directory(
            name="Create Docker systemd drop-in directory",
            path=DROP_IN_DIRECTORY,
            user="root",
            group="root",
            mode="0755",
        )
        result = files.put(
            name="Wait for both Caddy Tailscale listeners before Docker starts",
            src=StringIO(render_docker_startup(addresses)),
            dest=DROP_IN_PATH,
            user="root",
            group="root",
            mode="0644",
            add_deploy_dir=False,
        )
    else:
        result = files.file(
            name="Remove the homelab Docker startup gate when no longer needed",
            path=DROP_IN_PATH,
            present=False,
        )
    systemd.daemon_reload(
        name="Load changed Docker startup configuration without restarting Docker",
        _if=result.did_change,
    )
