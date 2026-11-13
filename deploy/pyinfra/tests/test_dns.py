import os
import shlex
import subprocess
from types import SimpleNamespace

import pytest
from pyinfra.api.exceptions import DeployError

from group_data import all as all_data
from group_data import gcp as gcp_data
from homelab_infra import dns

PROBES = ("example.com", "metadata.google.internal", "main.example.ts.net")


def test_dns_policy_is_explicit_and_only_opts_in_gcp() -> None:
    assert all_data.manage_resolved_dns is False
    assert all_data.dns_probe_names == ()
    assert gcp_data.manage_resolved_dns is True
    assert dns.dns_probe_names(gcp_data.dns_probe_names) == gcp_data.dns_probe_names


@pytest.mark.parametrize(
    "names", [(), ("a; reboot",), ("-bad.example",), ("a..b",), ("a.",), (None,)]
)
def test_invalid_probe_names_stop_before_entering_a_root_command(names) -> None:
    with pytest.raises(ValueError, match="valid hostnames"):
        dns.dns_probe_names(names)


@pytest.mark.parametrize(
    "connection,expected",
    [
        ("35.235.240.0 1234 10.0.0.1 22", True),
        ("35.235.255.255 1234 10.0.0.1 22", True),
        ("35.235.239.255 1234 10.0.0.1 22", False),
        ("100.64.0.1 1234 100.64.0.2 22", False),
        ("::1 1234 ::2 22", False),
        ("not-an-ip 1234 10.0.0.1 22", False),
        ("", False),
    ],
)
def test_migration_requires_the_independent_iap_connection(
    connection, expected
) -> None:
    assert dns.is_iap_connection(connection) is expected


@pytest.mark.parametrize("managed,configured", [(False, False), (True, True)])
def test_unmanaged_or_converged_hosts_have_no_operations(
    monkeypatch, managed, configured
) -> None:
    monkeypatch.setattr(
        dns,
        "host",
        SimpleNamespace(
            data=SimpleNamespace(manage_resolved_dns=managed, dns_probe_names=PROBES),
            get_fact=lambda *a, **kw: "configured" if configured else "",
        ),
    )
    monkeypatch.setattr(
        dns.server, "shell", lambda **kw: pytest.fail("No migration should be planned")
    )
    dns.configure_dns._inner()


@pytest.mark.parametrize("ready,iap", [(False, True), (True, False), (True, True)])
def test_prerequisites_and_transport_are_checked_before_mutations(
    monkeypatch, ready, iap
) -> None:
    operations = []

    def fact(*args, **kwargs):
        command = kwargs["command"]
        if command == dns.DNS_STATE_COMMAND:
            return ""
        if command == dns.PREREQUISITES:
            return "ready" if ready else ""
        assert kwargs["_sudo"] is False
        return f"{'35.235.248.2' if iap else '100.64.0.1'} 1234 10.0.0.1 22"

    monkeypatch.setattr(
        dns,
        "host",
        SimpleNamespace(
            data=SimpleNamespace(manage_resolved_dns=True, dns_probe_names=PROBES),
            get_fact=fact,
        ),
    )
    monkeypatch.setattr(dns.server, "shell", lambda **kw: operations.append(kw))
    if ready and iap:
        dns.configure_dns._inner()
        assert len(operations) == 1
    else:
        with pytest.raises(DeployError):
            dns.configure_dns._inner()
        assert not operations


@pytest.fixture
def dns_world(tmp_path):
    root = tmp_path / "root"
    for directory in [
        "etc",
        "run/systemd/resolve",
        "var/backups",
        "sys/class/net/tailscale0",
    ]:
        (root / directory).mkdir(parents=True, exist_ok=True)
    resolver = root / "etc/resolv.conf"
    resolver.write_text("# tailscale\nnameserver 100.100.100.100\n")
    stub = root / "run/systemd/resolve/stub-resolv.conf"
    stub.write_text("nameserver 127.0.0.53\n")
    upstream = root / "run/systemd/resolve/resolv.conf"
    upstream.write_text("nameserver 169.254.169.254\n")
    original_backup = root / "etc/resolv.pre-tailscale-backup.conf"
    original_backup.symlink_to(upstream)
    (root / "sys/class/net/tailscale0/ifindex").write_text("3\n")
    tools = tmp_path / "bin"
    tools.mkdir()
    scripts = {
        "systemctl": """\
case "$1" in
  is-active|is-enabled) test ! -f "$ROOT/$1-$3" ;;
  stop) if test "$2" = tailscaled; then
    rm -f "$ROOT/configured"
    if test -L "$ROOT/etc/resolv.pre-tailscale-backup.conf"; then
      mv -f "$ROOT/etc/resolv.pre-tailscale-backup.conf" "$ROOT/etc/resolv.conf"
    fi
  fi ;;
  start) if test "$2" = tailscaled; then touch "$ROOT/configured"; fi ;;
  *) exit 99 ;;
esac
""",
        "busctl": """\
if test -f "$ROOT/configured"; then echo 'a(iay) 1 2 4 100 100 100 100';
else echo 'a(iay) 0'; fi
""",
        "tailscale": "exit 0\n",
        "getent": "exit 0\n",
        "resolvectl": 'if test -f "$ROOT/fail_dns"; then exit 1; fi\n',
        "sleep": "exit 0\n",
        "ln": """\
if test -f "$ROOT/fail_link"; then exit 1; fi
exec /usr/bin/ln "$@"
""",
    }
    for name, body in scripts.items():
        f = tools / name
        f.write_text('#!/bin/sh\necho "' + name + ' $*" >> "$ROOT/log"\n' + body)
        f.chmod(0o700)

    def run(command):
        for path in [
            "/etc/resolv.pre-tailscale-backup.conf",
            "/etc/resolv.conf",
            "/run/systemd/resolve/stub-resolv.conf",
            "/var/backups/homelab-dns.",
            "/sys/class/net/tailscale0/ifindex",
        ]:
            command = command.replace(path, str(root) + path)
        env = {**os.environ, "PATH": f"{tools}:{os.environ['PATH']}", "ROOT": str(root)}
        return subprocess.run(
            ["/bin/sh", "-ec", command], env=env, text=True, capture_output=True
        )

    return root, resolver, original_backup, run


def test_generated_migration_preserves_data_and_converges(dns_world) -> None:
    root, resolver, _, run = dns_world
    assert run(dns.DNS_STATE_COMMAND).stdout == ""
    result = run(dns.build_dns_migration(PROBES))
    assert result.returncode == 0, result.stderr
    assert resolver.is_symlink()
    assert resolver.read_text() == "nameserver 127.0.0.53\n"
    assert run(dns.DNS_STATE_COMMAND).stdout == "configured"
    assert run(dns.build_dns_verification(PROBES)).returncode == 0
    backups = list((root / "var/backups").glob("homelab-dns.*"))
    assert len(backups) == 1
    assert (backups[0] / "resolv.conf").read_text().startswith("# tailscale")
    commands = (root / "log").read_text()
    assert commands.index("systemctl stop tailscaled") < commands.index("ln -sfnT")
    assert commands.index("ln -sfnT") < commands.index("systemctl start tailscaled")
    assert "docker" not in commands


@pytest.mark.parametrize("failure", ["fail_link", "fail_dns"])
def test_failed_promotion_or_dns_verification_restores_original_files(
    dns_world, failure
) -> None:
    root, resolver, original_backup, run = dns_world
    original = resolver.read_bytes()
    link_target = os.readlink(original_backup)
    (root / failure).touch()
    result = run(dns.build_dns_migration(PROBES))
    assert result.returncode != 0
    assert "restoration attempted" in result.stderr
    assert not resolver.is_symlink()
    assert resolver.read_bytes() == original
    assert os.readlink(original_backup) == link_target
    assert (root / "configured").exists()


def test_verification_rejects_wrong_stub_even_when_queries_would_pass(
    dns_world,
) -> None:
    root, _, _, run = dns_world
    (root / "configured").touch()
    result = run(dns.build_dns_verification(PROBES))
    assert result.returncode != 0
    if (root / "log").exists():
        assert "getent" not in (root / "log").read_text()


@pytest.mark.parametrize("service", ["systemd-resolved", "tailscaled"])
@pytest.mark.parametrize("check", ["is-active", "is-enabled"])
def test_each_required_service_must_be_active_and_enabled(
    dns_world, service, check
) -> None:
    root, _, _, run = dns_world
    assert run(dns.build_dns_migration(PROBES)).returncode == 0
    (root / f"{check}-{service}").touch()
    assert run(dns.DNS_STATE_COMMAND).stdout == ""
    assert run(dns.build_dns_verification(PROBES)).returncode != 0


def test_partial_stub_migration_still_requires_tailscale_registration(
    dns_world,
) -> None:
    _, resolver, _, run = dns_world
    resolver.unlink()
    resolver.symlink_to(resolver.parents[1] / "run/systemd/resolve/stub-resolv.conf")
    assert run(dns.DNS_STATE_COMMAND).stdout == ""


def test_scripts_are_valid_posix_shell(tmp_path) -> None:
    for script in [dns.build_dns_migration(PROBES), dns.build_dns_verification(PROBES)]:
        path = tmp_path / "script.sh"
        path.write_text(script)
        result = subprocess.run(
            ["/bin/sh", "-n", str(path)], capture_output=True, text=True
        )
        assert result.returncode == 0, result.stderr
    assert shlex.quote(PROBES[0]) in dns.build_dns_verification(PROBES)
