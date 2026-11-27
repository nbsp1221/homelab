import json
import re
import shlex
from io import StringIO
from pathlib import Path
from uuid import uuid4

from pyinfra import host, state
from pyinfra.api import deploy
from pyinfra.facts.server import Command, Home
from pyinfra.operations import files, server

REPO_ROOT = Path(__file__).resolve().parents[2]
APPLY_SCRIPT = REPO_ROOT / "pyinfra/files/apply_stack.sh"
COMPOSE_LOCK_DIRECTORY = "/run/homelab-compose"
MANAGED_STACKS = frozenset({"arcane", "arcane-agent", "caddy-gcp"})
CADDY_REQUIRED_VALUES = frozenset(
    {"CADDY_DOMAIN", "CADDY_BIND_IPV4", "CADDY_BIND_IPV6"}
)


def select_stacks(stacks: dict, selected: str | None) -> dict:
    if not isinstance(stacks, dict):
        raise ValueError("Invalid stack assignments")
    for stack, settings in stacks.items():
        if not isinstance(stack, str) or not re.fullmatch(
            r"[a-z0-9]+(?:-[a-z0-9]+)*", stack
        ):
            raise ValueError(f"Invalid stack name: {stack}")
        if (
            not isinstance(settings, dict)
            or set(settings) - {"bootstrap", "env"}
            or not isinstance(settings.get("bootstrap", False), bool)
        ):
            raise ValueError(f"Invalid settings for {stack}")
        env = settings.get("env", {})
        if not isinstance(env, dict) or any(
            not isinstance(key, str)
            or not re.fullmatch(r"[A-Z_][A-Z0-9_]*", key)
            or not isinstance(value, str)
            or "\n" in value
            or "\r" in value
            for key, value in env.items()
        ):
            raise ValueError(f"Invalid environment for {stack}")
    if selected is None:
        return {
            stack: settings
            for stack, settings in stacks.items()
            if not settings.get("bootstrap", False)
        }
    if selected not in stacks:
        raise ValueError(f"Stack is not assigned to this host: {selected}")
    return {selected: stacks[selected]}


def render_managed_env(environment: dict[str, str]) -> str:
    if not environment:
        return ""
    lines = ["# BEGIN HOMELAB HOST VALUES"]
    for key, value in environment.items():
        literal = json.dumps(value.replace("$", "$$"), ensure_ascii=False)
        lines.append(f"{key}={literal}")
    lines.append("# END HOMELAB HOST VALUES")
    return "\n".join(lines) + "\n"


def caddy_environment(settings: dict) -> dict[str, str]:
    environment = settings.get("env", {})
    if CADDY_REQUIRED_VALUES.difference(environment):
        raise ValueError("Load the private GCP ingress group data for Caddy")
    return environment


@deploy("Apply a Compose infrastructure stack")
def apply() -> None:
    selected = host.data.get("stack")
    if not selected or selected not in MANAGED_STACKS:
        raise ValueError(
            "Select an infrastructure stack: arcane, arcane-agent or caddy-gcp"
        )
    assignments = select_stacks(host.data.get("stacks", {}), selected)
    settings = assignments[selected]

    env_source = host.data.get("stack_env_file")
    if env_source:
        if state.config.DIFF:
            raise ValueError("Environment seeding cannot be used with --diff")
        env_source = Path(env_source).expanduser().resolve()
        if not env_source.is_file() or env_source.stat().st_mode & 0o077:
            raise ValueError(
                "Environment source must be a private local file (mode 600)"
            )

    project = REPO_ROOT / "stacks" / selected
    if not (project / "compose.yaml").is_file():
        project = REPO_ROOT / "compose" / selected
    if not (project / "compose.yaml").is_file():
        raise ValueError(f"Missing Compose project for {selected}")

    caddy = selected == "caddy-gcp"
    environment = caddy_environment(settings) if caddy else settings.get("env", {})
    assets = [("compose.yaml", str(project / "compose.yaml"))]
    if caddy:
        source = project / "config/Caddyfile"
        if not source.is_file() or source.is_symlink() or source.parent.is_symlink():
            raise ValueError("Missing or symlinked Caddyfile")
        assets.append(("config/Caddyfile", str(source)))
    if env_source:
        assets.append(("seed.env", str(env_source)))

    login = host.get_fact(Command, command="id -un", _sudo=False)
    owner = host.data.get("stack_owner", login)
    if not isinstance(owner, str) or not owner or not login:
        raise ValueError("Could not determine stack ownership")
    group = host.get_fact(
        Command, command=shlex.join(("id", "-gn", "--", owner)), _sudo=False
    )
    if not group:
        raise ValueError(f"Could not resolve the primary group for {owner}")
    bootstrap = settings.get("bootstrap", False)
    target = f"/opt/stacks/{selected}"
    if bootstrap:
        home = host.get_fact(Home, user=owner, _sudo=False)
        if not home or not Path(home).is_absolute():
            raise ValueError(f"Cannot resolve home for {owner}")
        target = f"{home}/compose/{selected}"
    stage = f"{target}/.deploy-{uuid4().hex}"
    ownership = {"user": owner, "group": group}
    files.directory(
        name=f"Create {selected} project directory",
        path=target,
        mode="700",
        _sudo=not bootstrap or owner != login,
        **ownership,
    )
    files.directory(
        name=f"Create private {selected} staging directory",
        path=stage,
        mode="700",
        **ownership,
    )
    for destination, source in assets:
        files.put(
            name=f"Stage {selected} {destination}",
            src=source,
            dest=f"{stage}/{destination}",
            mode="600",
            add_deploy_dir=False,
            **ownership,
        )
    files.put(
        name=f"Stage {selected} managed environment",
        src=StringIO(render_managed_env(environment)),
        dest=f"{stage}/managed.env",
        mode="600",
        **ownership,
    )
    files.directory(
        name="Create host-wide Compose lock directory",
        path=COMPOSE_LOCK_DIRECTORY,
        user="root",
        group="root",
        mode="755",
    )
    server.script(
        name=f"Validate and apply {selected}",
        src=str(APPLY_SCRIPT),
        args=(
            shlex.quote(target),
            shlex.quote(stage),
            "yes" if (project / ".env.example").is_file() else "no",
            "yes" if caddy else "no",
            COMPOSE_LOCK_DIRECTORY,
        ),
    )
