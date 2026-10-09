import json
import shlex
from io import StringIO
from pathlib import Path

from pyinfra import host, state
from pyinfra.facts.files import File
from pyinfra.operations import docker, files, server

from homelab_infra.hosts import REPO_ROOT, load_hosts
from homelab_infra.stacks import (
    load_stack_assets,
    render_environment_seed,
    select_stacks,
)

definition = load_hosts()[host.name]
selected = getattr(host.data, "stack", None)
env_source = getattr(host.data, "stack_env_file", None)
if env_source and (not selected or state.config.DIFF):
    raise ValueError("Environment seeding requires --data stack=... without --diff")
if env_source:
    env_source = Path(env_source).expanduser().resolve()
    if not env_source.is_file() or env_source.stat().st_mode & 0o077:
        raise ValueError("Environment source must be a private local file (mode 600)")

for stack, settings in select_stacks(definition["stacks"], selected).items():
    source = REPO_ROOT / "compose" / stack / "compose.yaml"
    if not source.is_file():
        raise ValueError(f"Missing Compose project: {source}")

    environment = settings.get("env", {})
    target = f"/opt/stacks/{stack}"
    ownership = {"user": host.data.ssh_user, "group": host.data.ssh_user}
    assets = load_stack_assets(source.parent)

    files.directory(
        name=f"Create {stack} project directory",
        path=target,
        **ownership,
        mode="700",
        _sudo=True,
    )
    seeding = env_source and not host.get_fact(File, path=f"{target}/.env")
    if seeding:
        # Operations are planned before execution. A later files.block would see
        # the absent remote file and replace the just-uploaded secret values.
        seed = render_environment_seed(env_source.read_text(), environment)
        files.put(
            name=f"Seed missing {stack} environment from a private local file",
            src=StringIO(seed),
            dest=f"{target}/.env",
            add_deploy_dir=False,
            **ownership,
            mode="600",
        )
    if (source.parent / ".env.example").is_file():
        server.shell(
            name=f"Require host-local {stack} environment file",
            commands=f"test -f {target}/.env",
        )
    if environment and not seeding:
        files.block(
            name=f"Sync {stack} non-secret host values",
            path=f"{target}/.env",
            content=[
                f"{key}={json.dumps(value)}" for key, value in environment.items()
            ],
            marker="# {mark} HOMELAB HOST VALUES",
        )
        files.file(
            name=f"Protect {stack} environment file",
            path=f"{target}/.env",
            **ownership,
            mode="600",
        )
    candidate = f"{target}/.deploy" if assets.files else target
    if assets.files:
        files.directory(
            name=f"Create {stack} candidate directory",
            path=candidate,
            **ownership,
            mode="700",
        )
    pending = f"{candidate}/compose.pending.yaml"
    compose = shlex.join(
        ["docker", "compose", "--project-directory", candidate]
        + (["--env-file", f"{target}/.env"] if assets.files else [])
        + ["-f", pending]
    )
    staged_files = [(asset, asset) for asset in assets.files]
    staged_files.append(("compose.yaml", "compose.pending.yaml"))
    for asset, destination in staged_files:
        files.put(
            name=f"Stage {stack} file {asset}",
            src=str(source.parent / asset),
            dest=f"{candidate}/{destination}",
            add_deploy_dir=False,
            **ownership,
            mode="600",
        )
    server.shell(
        name=f"Validate staged {stack} Compose configuration",
        commands=f"{compose} config --quiet",
        _env=environment,
    )
    for service, command in assets.checks:
        server.shell(
            name=f"Validate staged {stack} service {service}",
            commands=f"{compose} run --rm --no-deps {shlex.join([service, *command])}",
            _env=environment,
        )
    for asset in assets.files:
        files.directory(
            name=f"Create {stack} active asset directory for {asset}",
            path=str(Path(target, asset).parent),
            **ownership,
            mode="700",
        )
        server.shell(
            name=f"Promote validated {stack} asset {asset}",
            commands=shlex.join(
                ["cp", "--", f"{candidate}/{asset}", f"{target}/{asset}"]
            ),
        )
    server.shell(
        name=f"Promote validated {stack} Compose file",
        commands=shlex.join(["mv", "-f", pending, f"{target}/compose.yaml"]),
    )
    docker.compose(
        name=f"Apply {stack} Compose project",
        project_directory=target,
        remove_orphans=False,
        _env=environment,
    )
    if stack == "caddy-gcp":
        server.shell(
            name="Reload Caddy configuration without forcing container recreation",
            commands=(
                f"docker compose --project-directory {shlex.quote(target)} "
                "exec -T caddy caddy reload --config /etc/caddy/Caddyfile"
            ),
            _env=environment,
            # Compose may return before the new container's admin API is ready.
            _retries=3,
            _retry_delay=2,
        )
