from pyinfra import host
from pyinfra.operations import server

from homelab_infra.docker_startup import require_docker_startup
from homelab_infra.hosts import load_hosts
from homelab_infra.verification import build_baseline_verification

require_docker_startup(load_hosts()[host.name])

server.shell(
    name="Verify the complete host baseline",
    commands=build_baseline_verification(
        host.data.swap_path,
        host.data.swap_size_mb,
        tuple(host.data.docker_users),
    ),
)
