from pyinfra import host
from pyinfra.operations import server

from homelab_infra.verification import build_baseline_verification

server.shell(
    name="Verify the complete host baseline",
    commands=build_baseline_verification(
        host.data.swap_path,
        host.data.swap_size_mb,
        tuple(host.data.docker_users),
    ),
)
