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
    files.put(
        name=f"Upload {stack} Compose file",
        src=str(source),
        dest=f"{target}/compose.yaml",
        add_deploy_dir=False,
    )
    server.shell(
        name=f"Validate {stack} Compose configuration",
        commands=f"docker compose --project-directory {target} config --quiet",
        _env=environment,
    )
    docker.compose(
        name=f"Apply {stack} Compose project",
        project_directory=target,
        remove_orphans=False,
        _env=environment,
    )
