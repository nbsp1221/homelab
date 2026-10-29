import shlex
from io import StringIO
from ipaddress import ip_address

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.files import FileContents
from pyinfra.facts.server import Command
from pyinfra.operations import files, systemd

from homelab_infra.hosts import docker_tailscale_bind_addresses, load_hosts

DROP_IN_DIRECTORY = "/etc/systemd/system/docker.service.d"
DROP_IN_PATH = f"{DROP_IN_DIRECTORY}/10-homelab-tailscale.conf"
PREREQUISITES = (
    "test -x /usr/sbin/ip && test -x /usr/bin/grep && "
    "/usr/bin/tailscale wait --help >/dev/null 2>&1 && "
    "systemctl cat tailscaled.service >/dev/null 2>&1 && "
    "printf ready || true"
)
UNIT_STATE_COMMAND = (
    "systemctl show docker.service "
    "--property=LoadState --property=NeedDaemonReload --property=DropInPaths "
    "--property=ExecStartPre --property=Restart --property=RestartUSec "
    "--property=StartLimitIntervalUSec --property=Wants --property=After"
)


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
    # every declared host address, including usable IPv6.
    for value in addresses:
        address = ip_address(value)
        if "%" in str(address):
            raise ValueError("Scoped bind addresses are not supported")
        lines.append(
            "ExecStartPre=/bin/sh -ec '/usr/sbin/ip -o address show "
            f"to {address}/{address.max_prefixlen} "
            "-tentative -dadfailed | /usr/bin/grep -q .'"
        )
    lines.extend(["Restart=always", "RestartSec=10s", ""])
    return "\n".join(lines)


def docker_startup_is_loaded(addresses: tuple[str, ...], output: str) -> bool:
    properties = {}
    # systemctl can emit one ExecStartPre= line per command.
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            properties[key] = f"{properties.get(key, '')} {value}".strip()
    paths = properties.get("DropInPaths", "").split()
    if properties.get("NeedDaemonReload") == "yes":
        return False
    if not addresses:
        return DROP_IN_PATH not in paths
    if DROP_IN_PATH not in paths or properties.get("LoadState") != "loaded":
        return False
    if any(
        properties.get(key) != value
        for key, value in {
            "Restart": "always",
            "RestartUSec": "10s",
            "StartLimitIntervalUSec": "0",
        }.items()
    ):
        return False
    if any(
        "tailscaled.service" not in properties.get(key, "").split()
        for key in ("Wants", "After")
    ):
        return False
    commands = properties.get("ExecStartPre", "")
    return all(
        f"argv[]={' '.join(shlex.split(line.removeprefix('ExecStartPre=')))} "
        "; ignore_errors=no" in commands
        for line in render_docker_startup(addresses).splitlines()
        if line.startswith("ExecStartPre=")
    )


def require_docker_startup(definition: dict) -> None:
    addresses = docker_tailscale_bind_addresses(definition)
    if addresses is None:
        return
    contents = host.get_fact(FileContents, path=DROP_IN_PATH)
    expected = render_docker_startup(addresses).splitlines() if addresses else None
    loaded = host.get_fact(Command, command=UNIT_STATE_COMMAND)
    if contents != expected or not docker_startup_is_loaded(addresses, loaded):
        raise DeployError(
            "Docker startup policy differs on disk or in systemd; "
            "apply deploys/docker_startup.py for this host before deploying stacks"
        )


@deploy("Configure Docker startup dependencies")
def configure_docker_startup() -> None:
    addresses = docker_tailscale_bind_addresses(load_hosts()[host.name])
    if addresses is None:
        return
    loaded = host.get_fact(Command, command=UNIT_STATE_COMMAND)
    needs_reload = not docker_startup_is_loaded(addresses, loaded)
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
            name="Wait for declared Tailscale addresses before Docker starts",
            src=StringIO(render_docker_startup(addresses)),
            dest=DROP_IN_PATH,
            user="root",
            group="root",
            mode="0644",
            add_deploy_dir=False,
        )
    else:
        result = files.file(
            name="Explicitly disable the homelab Docker startup gate",
            path=DROP_IN_PATH,
            present=False,
        )
    systemd.daemon_reload(
        name="Load changed Docker startup configuration without restarting Docker",
        _if=lambda: result.did_change() or needs_reload,
    )
