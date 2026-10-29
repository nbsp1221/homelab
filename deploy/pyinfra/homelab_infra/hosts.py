import re
from ipaddress import ip_address
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
HOSTS_DIR = REPO_ROOT / "hosts"


def docker_tailscale_bind_addresses(definition: dict) -> tuple[str, ...] | None:
    """Return required addresses, () when disabled, or None when unmanaged."""
    if "docker" not in definition:
        return None
    settings = definition["docker"]
    if not isinstance(settings, dict) or set(settings) != {
        "wait_for_tailscale",
        "tailscale_bind_addresses",
    }:
        raise ValueError(
            "Docker settings require wait_for_tailscale and tailscale_bind_addresses"
        )
    enabled = settings["wait_for_tailscale"]
    if not isinstance(enabled, bool):
        raise ValueError("Docker wait_for_tailscale must be a boolean")
    values = settings["tailscale_bind_addresses"]
    if not isinstance(values, list) or any(
        not isinstance(value, str) for value in values
    ):
        raise ValueError("Docker tailscale_bind_addresses must be a list of IP strings")
    addresses = []
    for value in values:
        address = ip_address(value)
        if "%" in str(address) or address.is_unspecified or address.is_multicast:
            raise ValueError(
                "Docker bind addresses must be specific unscoped unicast IPs"
            )
        addresses.append(str(address))
    if len(set(addresses)) != len(addresses):
        raise ValueError("Duplicate Docker bind addresses")
    if enabled and not addresses:
        raise ValueError(
            "Enabled Docker startup policy requires at least one bind address"
        )
    return tuple(addresses) if enabled else ()


def load_hosts(hosts_dir: Path = HOSTS_DIR) -> dict[str, dict]:
    hosts = {}
    for path in sorted(hosts_dir.glob("*/host.yaml")):
        config = yaml.safe_load(path.read_text())
        if not isinstance(config, dict):
            raise ValueError(f"Invalid host definition: {path}")
        if config.get("provider") not in {"local", "gcp", "oci"}:
            raise ValueError(f"Invalid provider in {path}")
        docker_tailscale_bind_addresses(config)
        stacks = config.get("stacks")
        if not isinstance(stacks, dict):
            raise ValueError(f"Missing stack map in {path}")
        for stack, settings in stacks.items():
            if not isinstance(stack, str) or not re.fullmatch(
                r"[a-z0-9]+(?:-[a-z0-9]+)*", stack
            ):
                raise ValueError(f"Invalid stack name in {path}: {stack}")
            if not isinstance(settings, dict) or set(settings) - {"env"}:
                raise ValueError(f"Invalid settings for {stack} in {path}")
            env = settings.get("env", {})
            if not isinstance(env, dict) or any(
                not isinstance(key, str)
                or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key)
                or not isinstance(value, str)
                or "\n" in value
                or "\r" in value
                for key, value in env.items()
            ):
                raise ValueError(f"Invalid environment for {stack} in {path}")
        hosts[path.parent.name] = config
    return hosts
