import shlex
from ipaddress import ip_address

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.operations import server

from tasks.dns import dns_probe_names
from tasks.stacks import caddy_environment


def build_monitoring_verification(stacks: dict) -> str:
    if "caddy-gcp" not in stacks:
        return ""
    environment = caddy_environment(stacks["caddy-gcp"])
    domain = dns_probe_names((environment["CADDY_DOMAIN"],))[0]
    lines = ["set -eu", f"getent ahosts {shlex.quote(domain)} >/dev/null"]
    for version in (4, 6):
        address = ip_address(environment[f"CADDY_BIND_IPV{version}"])
        if address.version != version or "%" in str(address):
            raise ValueError(f"Monitoring requires an unscoped IPv{version} address")
        listener = str(address) if version == 4 else f"[{address}]"
        curl = shlex.join(
            [
                "curl",
                f"-{version}",
                "--noproxy",
                "*",
                "--fail",
                "--silent",
                "--show-error",
                "--connect-timeout",
                "5",
                "--max-time",
                "15",
                "--resolve",
                f"{domain}:443:{listener}",
            ]
        )
        lines.extend(
            [
                f"proxy_health=$({curl} https://{domain}/healthz)",
                'test "$proxy_health" = gcp-caddy-ok',
                f"hub_health=$({curl} https://{domain}/api/health)",
                "printf '%s' \"$hub_health\" | "
                "grep -Eq '\"code\"[[:space:]]*:[[:space:]]*200'",
                f"printf 'monitoring_ipv{version}=ok\\n'",
            ]
        )
    return "\n".join(lines)


@deploy("Verify the monitoring route")
def verify() -> None:
    commands = build_monitoring_verification(host.data.get("stacks", {}))
    if commands:
        server.shell(
            name="Verify the GCP proxy and Hub through TLS over both address families",
            commands=commands,
        )
