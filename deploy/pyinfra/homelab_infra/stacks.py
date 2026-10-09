import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StackAssets:
    files: tuple[str, ...] = ()
    checks: tuple[tuple[str, tuple[str, ...]], ...] = ()


def load_stack_assets(project: Path) -> StackAssets:
    if project.name != "caddy-gcp":
        return StackAssets()
    source = project / "config/Caddyfile"
    if not source.is_file() or source.is_symlink() or source.parent.is_symlink():
        raise ValueError("Missing or symlinked Caddyfile")
    return StackAssets(
        files=("config/Caddyfile",),
        checks=(("caddy", ("caddy", "validate", "--config", "/etc/caddy/Caddyfile")),),
    )


def select_stacks(stacks: dict, selected: str | None) -> dict:
    if selected is not None and selected not in stacks:
        raise ValueError(f"Stack is not assigned to this host: {selected}")
    return stacks if selected is None else {selected: stacks[selected]}


def render_environment_seed(secret_contents: str, environment: dict[str, str]) -> str:
    """Seed secrets and managed values together before remote facts exist."""
    if "# BEGIN HOMELAB HOST VALUES" in secret_contents:
        raise ValueError("Seed from a secret-only file without a host-values block")
    result = secret_contents.rstrip() + "\n"
    if environment:
        result += "\n# BEGIN HOMELAB HOST VALUES\n"
        result += "\n".join(
            f"{key}={json.dumps(value)}" for key, value in environment.items()
        )
        result += "\n# END HOMELAB HOST VALUES\n"
    return result
