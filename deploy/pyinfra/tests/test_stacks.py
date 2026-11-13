import runpy
from pathlib import Path
from types import SimpleNamespace

import pyinfra
import pytest
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


def test_stack_selection_cannot_apply_an_unassigned_project() -> None:
    stacks = {"beszel-agent": {}, "caddy-gcp": {}}
    assert select_stacks(stacks, "caddy-gcp") == {"caddy-gcp": {}}
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


@pytest.mark.parametrize("stack", ["caddy-gcp", "beszel-agent", "beszel-hub"])
def test_stack_plan_validates_before_promotion_and_reloads_only_caddy(
    tmp_path, monkeypatch, stack
) -> None:
    project = tmp_path / "compose" / stack
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
    names = [kwargs["name"] for _, kwargs in operations]
    uploads = [kwargs for op, kwargs in operations if op == "put"]
    assert {
        Path(upload["src"]).relative_to(project).as_posix() for upload in uploads
    } == (
        {"config/Caddyfile", "compose.yaml"}
        if stack == "caddy-gcp"
        else {"compose.yaml"}
    )
    assert all(upload["mode"] == "600" for upload in uploads)
    assert all(
        kwargs["mode"] == "700" for op, kwargs in operations if op == "directory"
    )
    assert (
        names.index(f"Validate staged {stack} Compose configuration")
        < names.index(f"Promote validated {stack} Compose file")
        < names.index(f"Apply {stack} Compose project")
    )
    if stack == "caddy-gcp":
        assert names.index("Validate staged caddy-gcp service caddy") < names.index(
            "Promote validated caddy-gcp asset config/Caddyfile"
        )
        assert operations[-1][0] == "shell"
        command = operations[-1][1]["commands"]
        assert "exec -T caddy caddy reload --config /etc/caddy/Caddyfile" in command
        assert "--force" not in command
        assert names.index("Apply caddy-gcp Compose project") == len(names) - 2
    else:
        assert operations[-1][0] == "compose"
