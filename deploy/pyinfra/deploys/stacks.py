import json

from pyinfra import host
from pyinfra.operations import docker, files, server

from homelab_infra.hosts import REPO_ROOT, load_hosts

definition = load_hosts()[host.name]

for stack, settings in definition["stacks"].items():
    source = REPO_ROOT / "compose" / stack / "compose.yaml"
    if not source.is_file():
        raise ValueError(f"Missing Compose project: {source}")

    environment = settings.get("env", {})
    target = f"/opt/stacks/{stack}"

    files.directory(
        name=f"Create {stack} project directory",
        path=target,
        user=host.data.ssh_user,
        mode="755",
        _sudo=True,
    )
    if (source.parent / ".env.example").is_file():
        server.shell(
            name=f"Require host-local {stack} environment file",
            commands=f"test -f {target}/.env",
        )
    if environment:
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
            mode="600",
        )
    files.put(
        name=f"Stage {stack} Compose file",
        src=str(source),
        dest=f"{target}/compose.pending.yaml",
        add_deploy_dir=False,
        user=host.data.ssh_user,
        group=host.data.ssh_user,
        mode="600",
    )
    server.shell(
        name=f"Validate staged {stack} Compose configuration",
        commands=(
            f"docker compose --project-directory {target} "
            f"-f {target}/compose.pending.yaml config --quiet"
        ),
        _env=environment,
    )
    server.shell(
        name=f"Promote validated {stack} Compose file",
        commands=f"mv -f {target}/compose.pending.yaml {target}/compose.yaml",
    )
    docker.compose(
        name=f"Apply {stack} Compose project",
        project_directory=target,
        remove_orphans=False,
        _env=environment,
    )
