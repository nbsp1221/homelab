import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
HOSTS_DIR = REPO_ROOT / "hosts"


def load_hosts(hosts_dir: Path = HOSTS_DIR) -> dict[str, dict]:
    hosts = {}
    for path in sorted(hosts_dir.glob("*/host.yaml")):
        config = yaml.safe_load(path.read_text())
        if not isinstance(config, dict):
            raise ValueError(f"Invalid host definition: {path}")
        if config.get("provider") not in {"local", "gcp", "oci"}:
            raise ValueError(f"Invalid provider in {path}")
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
                not isinstance(key, str) or not isinstance(value, str)
                for key, value in env.items()
            ):
                raise ValueError(f"Invalid environment for {stack} in {path}")
        hosts[path.parent.name] = config
    return hosts
