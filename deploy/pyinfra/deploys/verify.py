from pyinfra import host
from pyinfra.operations import server

from homelab_infra.dns import build_dns_verification
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

if host.data.manage_resolved_dns:
    server.shell(
        name="Verify managed host DNS policy",
        commands=build_dns_verification(tuple(host.data.dns_probe_names)),
    )
