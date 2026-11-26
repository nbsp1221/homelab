import runpy
import shlex
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pyinfra
import pytest
from pyinfra.facts.files import File
from pyinfra.facts.server import Home
from pyinfra.operations import docker, files, server

from homelab_infra import hosts
from homelab_infra.stacks import (
    StackAssets,
    load_stack_assets,
    render_environment_seed,
    select_stacks,
)


def test_compose_only_projects_do_not_upload_other_files(tmp_path) -> None:
    (tmp_path / ".env").write_text("secret")
    assert load_stack_assets(tmp_path) == StackAssets()


def test_caddy_uploads_only_its_public_configuration(tmp_path) -> None:
    project = tmp_path / "caddy-gcp"
    (project / "config").mkdir(parents=True)
    (project / "config/Caddyfile").write_text(":80 { respond ok }\n")
    (project / ".env").write_text("EXAMPLE_TOKEN=private\n")
    (project / "config/private.key").write_text("private")
    (project / "data").mkdir()
    (project / "data/identity").write_text("private")
    assert load_stack_assets(project) == StackAssets(
        files=("config/Caddyfile",),
        checks=(("caddy", ("caddy", "validate", "--config", "/etc/caddy/Caddyfile")),),
    )


@pytest.mark.parametrize("case", ["missing", "directory", "file-link", "parent-link"])
def test_caddy_rejects_missing_configuration_and_symlinks(tmp_path, case) -> None:
    project = tmp_path / "caddy-gcp"
    project.mkdir()
    original = tmp_path / "original"
    original.mkdir()
    (original / "Caddyfile").write_text("private")
    if case == "parent-link":
        (project / "config").symlink_to(original, target_is_directory=True)
    else:
        (project / "config").mkdir()
        if case == "file-link":
            (project / "config/Caddyfile").symlink_to(original / "Caddyfile")
        elif case == "directory":
            (project / "config/Caddyfile").mkdir()
    with pytest.raises(ValueError, match="Missing or symlinked Caddyfile"):
        load_stack_assets(project)


def test_stack_selection_requires_explicit_bootstrap_and_rejects_unassigned() -> None:
    stacks = {"example-app": {}, "bootstrap-agent": {"bootstrap": True}}
    assert select_stacks(stacks, None) == {"example-app": {}}
    assert select_stacks(stacks, "bootstrap-agent") == {
        "bootstrap-agent": {"bootstrap": True}
    }
    with pytest.raises(ValueError, match="not assigned"):
        select_stacks(stacks, "other")


def test_initial_environment_contains_secrets_and_host_values_together() -> None:
    result = render_environment_seed(
        "# private\nCLOUDFLARE_API_TOKEN=example-token\n",
        {"CADDY_DOMAIN": "beszel.example.com"},
    )
    assert result.startswith("# private\nCLOUDFLARE_API_TOKEN=example-token\n")
    assert 'CADDY_DOMAIN="beszel.example.com"' in result
    assert result.count("# BEGIN HOMELAB HOST VALUES") == 1


def test_initial_environment_refuses_to_import_another_hosts_managed_values() -> None:
    with pytest.raises(ValueError, match="secret-only"):
        render_environment_seed("# BEGIN HOMELAB HOST VALUES\n", {})


def test_deploy_rejects_an_assignment_without_a_compose_file(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(hosts, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        hosts, "load_hosts", lambda: {"cloud-a": {"stacks": {"example-app": {}}}}
    )
    monkeypatch.setattr(
        pyinfra, "host", SimpleNamespace(name="cloud-a", data=SimpleNamespace())
    )

    with pytest.raises(ValueError, match="Missing Compose project"):
        runpy.run_path(str(Path(__file__).parents[1] / "deploys/stacks.py"))


@pytest.mark.parametrize("has_env", [False, True])
def test_bootstrap_uses_operator_home_and_only_seeds_missing_env(
    tmp_path, monkeypatch, has_env
) -> None:
    name = "fake-cloud-host"
    user = "ssh-user"
    stack = "example-agent"
    home = "/custom/home/ssh-user"
    target = f"{home}/compose/{stack}"
    environment = {"EXAMPLE_AGENT_NAME": name}
    seed = tmp_path / "private.env"
    seed.write_text("EXAMPLE_REGISTRATION_KEY=test-placeholder\n")
    seed.chmod(0o600)
    project = tmp_path / "stacks" / stack
    project.mkdir(parents=True)
    (project / "compose.yaml").write_text("name: example\n")
    (project / ".env.example").write_text("EXAMPLE_REGISTRATION_KEY=\n")
    monkeypatch.setattr(hosts, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        hosts,
        "load_hosts",
        lambda: {name: {"stacks": {stack: {"bootstrap": True, "env": environment}}}},
    )

    def get_fact(fact, **kwargs):
        if fact is Home:
            assert kwargs == {"user": user}
            return home
        assert fact is File and kwargs == {"path": f"{target}/.env"}
        return {"mode": 600} if has_env else None

    monkeypatch.setattr(
        pyinfra,
        "host",
        SimpleNamespace(
            name=name,
            data=SimpleNamespace(ssh_user=user, stack=stack, stack_env_file=str(seed)),
            get_fact=get_fact,
        ),
    )
    monkeypatch.setattr(
        pyinfra, "state", SimpleNamespace(config=SimpleNamespace(DIFF=False))
    )
    for operation in ("directory", "put", "file", "block"):
        monkeypatch.setattr(files, operation, Mock())
    monkeypatch.setattr(server, "shell", Mock())
    monkeypatch.setattr(docker, "compose", Mock())
    runpy.run_path(str(Path(__file__).parents[1] / "deploys/stacks.py"))

    directory = files.directory.call_args.kwargs
    assert (directory["path"], directory["user"], directory["_sudo"]) == (
        target,
        user,
        False,
    )
    assert docker.compose.call_args.kwargs["project_directory"] == target
    env_uploads = [
        call.kwargs
        for call in files.put.call_args_list
        if call.kwargs["dest"].endswith("/.env")
    ]
    if has_env:
        assert not env_uploads
        assert files.block.call_args.kwargs["path"] == f"{target}/.env"
    else:
        (upload,) = env_uploads
        assert upload["mode"] == "600"
        assert "EXAMPLE_REGISTRATION_KEY=test-placeholder" in upload["src"].getvalue()
        assert f'EXAMPLE_AGENT_NAME="{name}"' in upload["src"].getvalue()
        files.block.assert_not_called()


@pytest.mark.parametrize(
    ("stack", "source_root"),
    [
        ("caddy-gcp", "compose"),
        ("beszel-agent", "compose"),
        ("beszel-hub", "stacks"),
        ("example-agent", "stacks"),
    ],
)
def test_stack_plan_validates_before_promotion_and_reloads_only_caddy(
    tmp_path, monkeypatch, stack, source_root
) -> None:
    project = tmp_path / source_root / stack
    project.mkdir(parents=True)
    (project / "compose.yaml").write_text("name: example\n")
    if stack == "caddy-gcp":
        (project / "config").mkdir()
        (project / "config/Caddyfile").write_text(":80 {\n respond ok\n}\n")
    monkeypatch.setattr(hosts, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(hosts, "load_hosts", lambda: {"test": {"stacks": {stack: {}}}})
    monkeypatch.setattr(
        pyinfra,
        "host",
        SimpleNamespace(name="test", data=SimpleNamespace(ssh_user="test")),
    )
    operations = []

    def record(operation):
        return lambda **kwargs: operations.append((operation, kwargs))

    for operation in ("directory", "put", "file", "block"):
        monkeypatch.setattr(files, operation, record(operation))
    monkeypatch.setattr(server, "shell", record("shell"))
    monkeypatch.setattr(docker, "compose", record("compose"))
    runpy.run_path(str(Path(__file__).parents[1] / "deploys/stacks.py"))

    applied = next(kwargs for op, kwargs in operations if op == "compose")
    assert not applied.get("force_recreate", False)
    assert applied["remove_orphans"] is False
    uploads = [kwargs for op, kwargs in operations if op == "put"]
    assert {
        Path(upload["src"]).relative_to(project).as_posix() for upload in uploads
    } == (
        {"config/Caddyfile", "compose.yaml"}
        if stack == "caddy-gcp"
        else {"compose.yaml"}
    )
    assert all(upload["mode"] == "600" for upload in uploads)
    commands = {
        index: shlex.split(kwargs["commands"])
        for index, (op, kwargs) in enumerate(operations)
        if op == "shell"
    }
    validate = next(
        i for i, args in commands.items() if args[-2:] == ["config", "--quiet"]
    )
    promote = next(i for i, args in commands.items() if args[0] == "mv")
    apply = next(i for i, (op, _) in enumerate(operations) if op == "compose")
    assert validate < promote < apply
    reloads = {
        i: args for i, args in commands.items() if "caddy" in args and "reload" in args
    }
    if stack == "caddy-gcp":
        caddy_check = next(
            i for i, args in commands.items() if "caddy" in args and "validate" in args
        )
        assert validate < caddy_check < promote
        ((reload_at, args),) = reloads.items()
        assert reload_at > apply
        assert "--force" not in args
    else:
        assert not reloads
