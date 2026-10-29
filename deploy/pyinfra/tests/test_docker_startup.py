import shlex
import subprocess
from types import SimpleNamespace

import pytest
from pyinfra.api.exceptions import DeployError

from homelab_infra import docker_startup
from homelab_infra.hosts import load_hosts


def test_only_the_caddy_host_waits_for_its_declared_bind_addresses() -> None:
    definitions = load_hosts()
    assert docker_startup.tailscale_bind_addresses(definitions["retn0-srv-gcp-01"]) == (
        "100.82.114.104",
        "fd7a:115c:a1e0::7536:7269",
    )
    for name, definition in definitions.items():
        if name != "retn0-srv-gcp-01":
            assert docker_startup.tailscale_bind_addresses(definition) == ()


@pytest.mark.parametrize(
    "version,value",
    [
        (4, ""),
        (4, "not-an-ip"),
        (4, "::1"),
        (4, "1.2.3.4; reboot"),
        (6, "1.2.3.4"),
        (6, "fd7a::1%tailscale0"),
        (6, "fd7a::1%x'; reboot; '"),
    ],
)
def test_bad_bind_addresses_cannot_reach_a_root_shell(version, value) -> None:
    environment = {"CADDY_BIND_IPV4": "100.64.0.1", "CADDY_BIND_IPV6": "fd7a::1"}
    environment[f"CADDY_BIND_IPV{version}"] = value
    with pytest.raises(ValueError):
        docker_startup.tailscale_bind_addresses(
            {"stacks": {"caddy-gcp": {"env": environment}}}
        )


def test_startup_gate_keeps_retrying_without_replacing_dockers_main_process() -> None:
    content = docker_startup.render_docker_startup(("100.64.0.1", "fd7a::1"))
    assert "Wants=tailscaled.service\nAfter=tailscaled.service" in content
    assert "StartLimitIntervalSec=0" in content
    assert "ExecStartPre=/usr/bin/tailscale wait --timeout=60s" in content
    assert "Restart=always\nRestartSec=10s" in content
    assert "ExecStart=" not in content
    assert "Requires=" not in content
    assert "to 100.64.0.1/32" in content
    assert "to fd7a::1/128" in content
    assert content.count("-tentative -dadfailed") == 2


@pytest.mark.parametrize(
    "ipv4_ready,ipv6_ready", [(False, True), (True, False), (True, True)]
)
def test_both_real_interface_checks_must_pass_before_docker_can_start(
    tmp_path, ipv4_ready, ipv6_ready
) -> None:
    fake_ip = tmp_path / "ip"
    fake_ip.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f"  *100.64.0.1/32*) {'echo inet' if ipv4_ready else 'exit 0'} ;;\n"
        f"  *fd7a::1/128*) {'echo inet6' if ipv6_ready else 'exit 0'} ;;\n"
        "  *) exit 1 ;;\nesac\n"
    )
    fake_ip.chmod(0o700)
    content = docker_startup.render_docker_startup(("100.64.0.1", "fd7a::1"))
    checks = [
        line.removeprefix("ExecStartPre=").replace("/usr/sbin/ip", str(fake_ip))
        for line in content.splitlines()
        if line.startswith("ExecStartPre=/bin/sh")
    ]
    results = [subprocess.run(shlex.split(check), check=False) for check in checks]
    assert [result.returncode == 0 for result in results] == [ipv4_ready, ipv6_ready]


@pytest.mark.parametrize(
    "enabled,changed", [(True, True), (True, False), (False, True), (False, False)]
)
def test_configuration_only_reloads_changed_units_and_never_restarts_containers(
    monkeypatch, enabled, changed
) -> None:
    operations = []

    def did_change():
        return changed

    def record(operation):
        def execute(**kwargs):
            operations.append((operation, kwargs))
            return SimpleNamespace(did_change=did_change)

        return execute

    monkeypatch.setattr(
        docker_startup,
        "load_hosts",
        lambda: {
            "test": {
                "stacks": load_hosts()["retn0-srv-gcp-01"]["stacks"] if enabled else {}
            }
        },
    )
    monkeypatch.setattr(
        docker_startup,
        "host",
        SimpleNamespace(name="test", get_fact=lambda *args, **kwargs: "ready"),
    )
    for operation in ("directory", "put", "file"):
        monkeypatch.setattr(docker_startup.files, operation, record(operation))
    monkeypatch.setattr(docker_startup.systemd, "daemon_reload", record("reload"))
    monkeypatch.setattr(
        docker_startup.systemd,
        "service",
        lambda **kwargs: pytest.fail("Startup configuration must not control Docker"),
    )
    docker_startup.configure_docker_startup._inner()
    assert [operation for operation, _ in operations] == (
        ["directory", "put", "reload"] if enabled else ["file", "reload"]
    )
    update = operations[-2][1]
    assert update.get("dest", update.get("path")) == docker_startup.DROP_IN_PATH
    if enabled:
        assert update["user"] == update["group"] == "root"
        assert update["mode"] == "0644"
    else:
        assert update["present"] is False
    assert operations[-1][1]["_if"]() is changed


def test_missing_tailscale_support_stops_before_any_configuration_write(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        docker_startup,
        "host",
        SimpleNamespace(name="retn0-srv-gcp-01", get_fact=lambda *args, **kwargs: ""),
    )
    monkeypatch.setattr(
        docker_startup.files,
        "directory",
        lambda **kwargs: pytest.fail("Preflight must run before configuration writes"),
    )
    with pytest.raises(DeployError, match="requires tailscale wait"):
        docker_startup.configure_docker_startup._inner()
