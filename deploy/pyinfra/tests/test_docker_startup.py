import runpy
import shlex
import subprocess
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import pyinfra
import pytest
import yaml
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.files import FileContents
from pyinfra.operations import docker, server

from homelab_infra import docker_startup, hosts
from homelab_infra.hosts import docker_tailscale_bind_addresses, load_hosts

ADDRESSES = ("100.64.0.1", "fd7a::1")


def definition(addresses=ADDRESSES):
    return {
        "docker": {
            "wait_for_tailscale": bool(addresses),
            "tailscale_bind_addresses": list(addresses),
        },
        "stacks": {},
    }


def loaded_state(addresses=ADDRESSES, **overrides):
    commands = " ".join(
        "{ argv[]="
        + " ".join(shlex.split(line.removeprefix("ExecStartPre=")))
        + " ; ignore_errors=no ; }"
        for line in docker_startup.render_docker_startup(addresses).splitlines()
        if line.startswith("ExecStartPre=")
    )
    properties = {
        "LoadState": "loaded",
        "NeedDaemonReload": "no",
        "DropInPaths": docker_startup.DROP_IN_PATH,
        "ExecStartPre": commands,
        "Restart": "always",
        "RestartUSec": "10s",
        "StartLimitIntervalUSec": "0",
        "Wants": "containerd.service tailscaled.service",
        "After": "network-online.target tailscaled.service",
    }
    properties.update(overrides)
    return "\n".join(f"{key}={value}" for key, value in properties.items())


def test_host_policy_survives_stack_rename_and_unassignment() -> None:
    original = load_hosts()["retn0-srv-gcp-01"]
    expected = docker_tailscale_bind_addresses(original)
    assert expected
    renamed = deepcopy(original)
    renamed["stacks"]["proxy"] = renamed["stacks"].pop("caddy-gcp")
    assert docker_tailscale_bind_addresses(renamed) == expected
    renamed["stacks"].clear()
    assert docker_tailscale_bind_addresses(renamed) == expected


def test_changing_the_only_address_source_updates_the_host_and_application(
    tmp_path,
) -> None:
    source = (hosts.HOSTS_DIR / "retn0-srv-gcp-01/host.yaml").read_text()
    old = load_hosts()["retn0-srv-gcp-01"]["docker"]["tailscale_bind_addresses"][0]
    assert source.count(old) == 1
    host_dir = tmp_path / "example"
    host_dir.mkdir()
    (host_dir / "host.yaml").write_text(source.replace(old, "100.64.0.50"))
    changed = load_hosts(tmp_path)["example"]
    addresses = docker_tailscale_bind_addresses(changed)
    assert addresses[0] == "100.64.0.50"
    assert changed["stacks"]["caddy-gcp"]["env"]["CADDY_BIND_IPV4"] == addresses[0]
    rendered = docker_startup.render_docker_startup(addresses)
    assert "100.64.0.50/32" in rendered and old not in rendered


def test_disabling_policy_keeps_application_address_aliases_valid(tmp_path) -> None:
    source = (hosts.HOSTS_DIR / "retn0-srv-gcp-01/host.yaml").read_text()
    host_dir = tmp_path / "example"
    host_dir.mkdir()
    (host_dir / "host.yaml").write_text(
        source.replace("wait_for_tailscale: true", "wait_for_tailscale: false")
    )
    disabled = load_hosts(tmp_path)["example"]
    assert docker_tailscale_bind_addresses(disabled) == ()
    assert disabled["stacks"] == load_hosts()["retn0-srv-gcp-01"]["stacks"]


@pytest.mark.parametrize(
    "settings",
    [
        None,
        {},
        {"tailscale_bind_addresses": None},
        {"tailscale_bind_addresses": "100.64.0.1"},
        {"tailscale_bind_addresses": [123]},
        {"tailscale_bind_addresses": ["not-an-ip"]},
        {"tailscale_bind_addresses": ["0.0.0.0"]},
        {"tailscale_bind_addresses": ["::"]},
        {"tailscale_bind_addresses": ["ff02::1"]},
        {"tailscale_bind_addresses": []},
        {"tailscale_bind_addresses": ["100.64.0.1"], "wait_for_tailscale": "false"},
        {"tailscale_bind_addresses": ["1.2.3.4; reboot"]},
        {"tailscale_bind_addresses": ["fd7a::1%tailscale0"]},
        {"tailscale_bind_addresses": ["fd7a::1%x'; reboot; '"]},
        {"tailscale_bind_addresses": ["fd7a::1", "fd7a:0:0:0:0:0:0:1"]},
        {"tailscale_bind_addresses": [], "typo": True},
    ],
)
def test_invalid_policy_is_rejected_while_loading_inventory(tmp_path, settings) -> None:
    host_dir = tmp_path / "example"
    host_dir.mkdir()
    (host_dir / "host.yaml").write_text(
        yaml.safe_dump(
            {
                "provider": "gcp",
                "stacks": {},
                "docker": {"wait_for_tailscale": True, **settings}
                if isinstance(settings, dict)
                else settings,
            }
        )
    )
    with pytest.raises(ValueError):
        load_hosts(tmp_path)


def test_startup_gate_retries_without_replacing_dockers_main_process() -> None:
    content = docker_startup.render_docker_startup(ADDRESSES)
    assert "StartLimitIntervalSec=0" in content
    assert "ExecStartPre=/usr/bin/tailscale wait --timeout=60s" in content
    assert "Restart=always\nRestartSec=10s" in content
    assert "ExecStart=" not in content and "Requires=" not in content
    assert "dev " not in content
    assert content.count("-tentative -dadfailed") == 2


@pytest.mark.parametrize(
    "ipv4_ready,ipv6_ready", [(False, True), (True, False), (True, True)]
)
def test_every_declared_address_must_be_ready(tmp_path, ipv4_ready, ipv6_ready) -> None:
    fake_ip = tmp_path / "ip"
    fake_ip.write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        f"  *100.64.0.1/32*) {'echo inet' if ipv4_ready else 'exit 0'} ;;\n"
        f"  *fd7a::1/128*) {'echo inet6' if ipv6_ready else 'exit 0'} ;;\n"
        "  *) exit 1 ;;\nesac\n"
    )
    fake_ip.chmod(0o700)
    checks = [
        line.removeprefix("ExecStartPre=").replace("/usr/sbin/ip", str(fake_ip))
        for line in docker_startup.render_docker_startup(ADDRESSES).splitlines()
        if line.startswith("ExecStartPre=/bin/sh")
    ]
    results = [subprocess.run(shlex.split(check), check=False) for check in checks]
    assert [result.returncode == 0 for result in results] == [ipv4_ready, ipv6_ready]


@pytest.mark.parametrize(
    "overrides",
    [
        {"NeedDaemonReload": "yes"},
        {"DropInPaths": ""},
        {"ExecStartPre": ""},
        {"ExecStartPre": "{ argv[]=/usr/bin/true ; ignore_errors=yes ; }"},
        {"RestartUSec": "2s"},
        {"StartLimitIntervalUSec": "1min"},
        {"After": "network-online.target"},
        {"Wants": "containerd.service"},
    ],
)
def test_loaded_state_checks_effective_configuration_not_only_reload_flag(
    overrides,
) -> None:
    assert not docker_startup.docker_startup_is_loaded(
        ADDRESSES, loaded_state(**overrides)
    )


def test_loaded_state_accepts_repeated_systemctl_command_properties() -> None:
    output = loaded_state().replace(" ; } { argv[]=", " ; }\nExecStartPre={ argv[]=")
    assert output.count("\nExecStartPre=") == 3
    assert docker_startup.docker_startup_is_loaded(ADDRESSES, output)


@pytest.mark.parametrize(
    "changed,loaded", [(True, True), (False, True), (False, False)]
)
def test_apply_recovers_interrupted_reload_without_restarting_services(
    monkeypatch, changed, loaded
) -> None:
    operations = []

    def record(operation):
        def execute(**kwargs):
            operations.append((operation, kwargs))
            return SimpleNamespace(did_change=lambda: changed)

        return execute

    monkeypatch.setattr(docker_startup, "load_hosts", lambda: {"test": definition()})
    monkeypatch.setattr(
        docker_startup,
        "host",
        SimpleNamespace(
            name="test",
            get_fact=lambda fact, command: (
                "ready"
                if command == docker_startup.PREREQUISITES
                else loaded_state(
                    DropInPaths=docker_startup.DROP_IN_PATH if loaded else ""
                )
            ),
        ),
    )
    for operation in ("directory", "put"):
        monkeypatch.setattr(docker_startup.files, operation, record(operation))
    monkeypatch.setattr(docker_startup.systemd, "daemon_reload", record("reload"))
    monkeypatch.setattr(
        docker_startup.systemd,
        "service",
        lambda **kwargs: pytest.fail("Must not restart"),
    )
    docker_startup.configure_docker_startup._inner()
    assert [operation for operation, _ in operations] == ["directory", "put", "reload"]
    assert operations[-1][1]["_if"]() is (changed or not loaded)


def test_absent_policy_leaves_existing_configuration_unmanaged(monkeypatch) -> None:
    monkeypatch.setattr(docker_startup, "load_hosts", lambda: {"test": {"stacks": {}}})
    monkeypatch.setattr(
        docker_startup,
        "host",
        SimpleNamespace(
            name="test", get_fact=lambda *a, **kw: pytest.fail("No host reads")
        ),
    )
    monkeypatch.setattr(
        docker_startup.files,
        "file",
        lambda **kw: pytest.fail("Must not infer deletion"),
    )
    docker_startup.configure_docker_startup._inner()
    docker_startup.require_docker_startup({"stacks": {}})


def test_only_explicit_disabled_policy_removes_the_owned_drop_in(monkeypatch) -> None:
    operations = []
    monkeypatch.setattr(docker_startup, "load_hosts", lambda: {"test": definition(())})
    monkeypatch.setattr(
        docker_startup,
        "host",
        SimpleNamespace(name="test", get_fact=lambda *a, **kw: loaded_state()),
    )
    monkeypatch.setattr(
        docker_startup.files,
        "file",
        lambda **kw: operations.append(kw) or SimpleNamespace(did_change=lambda: True),
    )
    monkeypatch.setattr(docker_startup.systemd, "daemon_reload", lambda **kw: None)
    docker_startup.configure_docker_startup._inner()
    assert len(operations) == 1
    assert operations[0]["path"] == docker_startup.DROP_IN_PATH
    assert operations[0]["present"] is False
    assert docker_startup.docker_startup_is_loaded((), loaded_state(DropInPaths=""))
    assert not docker_startup.docker_startup_is_loaded((), loaded_state())


@pytest.mark.parametrize(
    "disk_current,unit_current", [(False, True), (True, False), (True, True)]
)
def test_stack_preflight_checks_disk_and_loaded_state_before_any_writes(
    tmp_path, monkeypatch, disk_current, unit_current
) -> None:
    desired = definition(("100.64.0.50", "fd7a::1"))
    desired["stacks"] = {"example": {"env": {"LISTEN_IPV4": "100.64.0.50"}}}
    project = tmp_path / "compose/example"
    project.mkdir(parents=True)
    (project / "compose.yaml").write_text("name: example\n")
    monkeypatch.setattr(hosts, "REPO_ROOT", tmp_path)
    contents = docker_startup.render_docker_startup(
        docker_tailscale_bind_addresses(desired) if disk_current else ADDRESSES
    ).splitlines()
    state = loaded_state(("100.64.0.50", "fd7a::1") if unit_current else ADDRESSES)
    monkeypatch.setattr(
        docker_startup,
        "host",
        SimpleNamespace(
            get_fact=lambda fact, **kwargs: contents if fact is FileContents else state
        ),
    )
    monkeypatch.setattr(hosts, "load_hosts", lambda: {"test": desired})
    monkeypatch.setattr(
        pyinfra,
        "host",
        SimpleNamespace(name="test", data=SimpleNamespace(ssh_user="test")),
    )
    operations = []

    def record(operation):
        return lambda **kwargs: operations.append((operation, kwargs))

    for operation in ("directory", "put", "file", "block"):
        monkeypatch.setattr(docker_startup.files, operation, record(operation))
    monkeypatch.setattr(server, "shell", record("shell"))
    monkeypatch.setattr(docker, "compose", record("compose"))
    path = str(Path(__file__).parents[1] / "deploys/stacks.py")
    if disk_current and unit_current:
        runpy.run_path(path)
        env = next(kwargs for op, kwargs in operations if op == "block")
        assert 'LISTEN_IPV4="100.64.0.50"' in env["content"]
        assert operations[-1][0] == "compose"
    else:
        with pytest.raises(DeployError, match="apply deploys/docker_startup.py"):
            runpy.run_path(path)
        assert operations == []


def test_missing_wait_support_stops_before_any_configuration_write(monkeypatch) -> None:
    monkeypatch.setattr(docker_startup, "load_hosts", lambda: {"test": definition()})
    monkeypatch.setattr(
        docker_startup,
        "host",
        SimpleNamespace(name="test", get_fact=lambda *args, **kwargs: ""),
    )
    monkeypatch.setattr(
        docker_startup.files,
        "directory",
        lambda **kwargs: pytest.fail("Must preflight first"),
    )
    with pytest.raises(DeployError, match="requires tailscale wait"):
        docker_startup.configure_docker_startup._inner()
