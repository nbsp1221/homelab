import re
import shlex
from ipaddress import ip_address, ip_network
from textwrap import dedent

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.server import Command
from pyinfra.operations import server

IAP_RANGE = ip_network("35.235.240.0/20")
STUB_PATH = "/run/systemd/resolve/stub-resolv.conf"
RESOLV_PATH = "/etc/resolv.conf"
TAILSCALE_BACKUP = "/etc/resolv.pre-tailscale-backup.conf"
DNS_READY = dedent(
    f"""\
    test "$(readlink -f {RESOLV_PATH})" = {STUB_PATH} &&
    systemctl is-active --quiet systemd-resolved &&
    systemctl is-active --quiet tailscaled &&
    systemctl is-enabled --quiet systemd-resolved &&
    systemctl is-enabled --quiet tailscaled &&
    index=$(cat /sys/class/net/tailscale0/ifindex) &&
    busctl --system --auto-start=no get-property org.freedesktop.resolve1 \
      "/org/freedesktop/resolve1/link/$index" org.freedesktop.resolve1.Link DNS \
      | grep -Eq '(^| )2 4 100 100 100 100( |$)'
    """
).strip()
DNS_STATE_COMMAND = f"if {DNS_READY}; then printf configured; fi"
PREREQUISITES = dedent(
    f"""\
    if test -r {STUB_PATH} && test -r {RESOLV_PATH} &&
      ! test -d {RESOLV_PATH} &&
      systemctl is-enabled --quiet systemd-resolved &&
      systemctl is-enabled --quiet tailscaled &&
      command -v busctl getent resolvectl timeout >/dev/null &&
      tailscale wait --help >/dev/null 2>&1; then printf ready; fi
    """
)


def dns_probe_names(values: tuple[str, ...]) -> tuple[str, ...]:
    if not values or any(
        not isinstance(value, str)
        or len(value) > 253
        or any(
            not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in value.split(".")
        )
        for value in values
    ):
        raise ValueError("DNS probes must be nonempty, valid hostnames")
    return tuple(values)


def is_iap_connection(connection: str) -> bool:
    fields = connection.split()
    if len(fields) != 4:
        return False
    try:
        return ip_address(fields[0]) in IAP_RANGE
    except ValueError:
        return False


def build_dns_verification(probes: tuple[str, ...]) -> str:
    names = shlex.join(dns_probe_names(probes))
    return dedent(
        f"""\
        set -eu
        if ! {{ {DNS_READY}; }}; then
          echo 'DNS must use the resolved stub and Tailscale link DNS' >&2
          exit 1
        fi
        for name in {names}; do
          timeout 10 getent ahostsv4 "$name" >/dev/null
          timeout 10 resolvectl query --cache=no --type=A "$name" >/dev/null
          printf 'dns_ok=%s\\n' "$name"
        done
        """
    )


def build_dns_migration(probes: tuple[str, ...]) -> str:
    verification = shlex.quote(build_dns_verification(probes))
    # Keep stop/link/start in one remote command so a failed promotion can restore
    # both DNS files before pyinfra aborts. This must run over the independent IAP path.
    return dedent(
        f"""\
        set -eu
        umask 077
        backup=$(mktemp -d /var/backups/homelab-dns.XXXXXX)
        cp -a -- {RESOLV_PATH} "$backup/resolv.conf"
        if test -e {TAILSCALE_BACKUP} || test -L {TAILSCALE_BACKUP}; then
          cp -a -- {TAILSCALE_BACKUP} "$backup/tailscale-backup"
        fi
        rollback() {{
          status=$?
          trap - EXIT HUP INT TERM
          set +e
          systemctl stop tailscaled
          rm -f -- {RESOLV_PATH}
          cp -a -- "$backup/resolv.conf" {RESOLV_PATH}
          rm -f -- {TAILSCALE_BACKUP}
          if test -e "$backup/tailscale-backup" ||
            test -L "$backup/tailscale-backup"; then
            cp -a -- "$backup/tailscale-backup" {TAILSCALE_BACKUP}
          fi
          systemctl start tailscaled
          printf 'DNS migration failed; restoration attempted from %s\\n' "$backup" >&2
          exit "$status"
        }}
        trap rollback EXIT
        trap 'exit 129' HUP
        trap 'exit 130' INT
        trap 'exit 143' TERM
        systemctl stop tailscaled
        systemctl start systemd-resolved
        ln -sfnT -- {STUB_PATH} {RESOLV_PATH}
        systemctl start tailscaled
        tailscale wait --timeout=60s
        verified=false
        for attempt in 1 2 3 4 5; do
          if /bin/sh -ec {verification}; then verified=true; break; fi
          sleep 2
        done
        test "$verified" = true
        trap - EXIT HUP INT TERM
        printf 'DNS configured; rollback files retained in %s\\n' "$backup"
        """
    )


@deploy("Configure systemd-resolved DNS integration")
def configure_dns() -> None:
    if not host.data.manage_resolved_dns:
        return
    try:
        probes = dns_probe_names(tuple(host.data.dns_probe_names))
    except ValueError as error:
        raise DeployError(str(error)) from error
    if host.get_fact(Command, command=DNS_STATE_COMMAND) == "configured":
        return
    if host.get_fact(Command, command=PREREQUISITES) != "ready":
        raise DeployError(
            "DNS migration requires existing enabled systemd-resolved/Tailscale, "
            "the resolver files and DNS verification tools; install/enroll separately"
        )
    connection = host.get_fact(
        Command, command='printf "%s" "$SSH_CONNECTION"', _sudo=False
    )
    if not is_iap_connection(connection):
        raise DeployError(
            "DNS migration stops Tailscale: use the independent GCP IAP SSH alias "
            "with --data ssh_hostname=<iap-alias>"
        )
    server.shell(
        name="Migrate DNS over IAP with local rollback and native DNS checks",
        commands=build_dns_migration(probes),
    )
