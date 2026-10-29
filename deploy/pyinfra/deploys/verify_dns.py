from pyinfra import host
from pyinfra.operations import server

from homelab_infra.dns import build_dns_verification

if host.data.manage_resolved_dns:
    server.shell(
        name="Verify resolver integration and public, cloud and Tailscale DNS",
        commands=build_dns_verification(tuple(host.data.dns_probe_names)),
    )
