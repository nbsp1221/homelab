from pyinfra import host
from pyinfra.operations import server

from homelab_infra.hosts import load_hosts
from homelab_infra.monitoring import build_monitoring_verification

commands = build_monitoring_verification(load_hosts()[host.name])
if commands:
    server.shell(
        name="Verify the GCP proxy and Hub through TLS over both address families",
        commands=commands,
    )
