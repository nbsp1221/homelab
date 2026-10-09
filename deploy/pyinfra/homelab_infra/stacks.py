import json
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import yaml


@dataclass(frozen=True)
class StackAssets:
    files: tuple[str, ...] = ()
    checks: tuple[tuple[str, tuple[str, ...]], ...] = ()


def load_stack_assets(project: Path) -> StackAssets:
    """Read an explicit allowlist of public project assets, never runtime state."""
    manifest = project / "deploy.yaml"
    if not manifest.is_file():
        return StackAssets()
    config = yaml.safe_load(manifest.read_text())
    if not isinstance(config, dict) or set(config) - {"files", "checks"}:
        raise ValueError(f"Invalid stack deployment manifest: {manifest}")
    paths = config.get("files", [])
    if not isinstance(paths, list) or any(not isinstance(p, str) for p in paths):
        raise ValueError(f"Invalid asset list in {manifest}")
    if len(set(paths)) != len(paths):
        raise ValueError(f"Duplicate asset in {manifest}")
    for value in paths:
        path = PurePosixPath(value)
        if (
            not path.parts
            or path.is_absolute()
            or value != path.as_posix()
            or ".." in path.parts
            or any(p.startswith(".env") or p == "data" for p in path.parts)
            or path.name in {"compose.yaml", "deploy.yaml"}
            or path.suffix in {".pem", ".key"}
        ):
            raise ValueError(f"Unsafe deployment asset: {value}")
        source = project / value
        if not source.is_file() or not source.resolve().is_relative_to(
            project.resolve()
        ):
            raise ValueError(f"Missing or escaped deployment asset: {value}")
        if any(
            (project / Path(*path.parts[:i])).is_symlink()
            for i in range(1, len(path.parts) + 1)
        ):
            raise ValueError(f"Symlink deployment asset: {value}")
    checks = config.get("checks", {})
    if not isinstance(checks, dict):
        raise ValueError(f"Invalid checks in {manifest}")
    for service, command in checks.items():
        if (
            not isinstance(service, str)
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", service)
            or not isinstance(command, list)
            or not command
            or any(not isinstance(arg, str) or not arg for arg in command)
        ):
            raise ValueError(f"Invalid service check in {manifest}")
    return StackAssets(tuple(paths), tuple((s, tuple(c)) for s, c in checks.items()))


def select_stacks(stacks: dict, selected: str | None) -> dict:
    if selected is None:
        return stacks
    if selected not in stacks:
        raise ValueError(f"Stack is not assigned to this host: {selected}")
    return {selected: stacks[selected]}


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
