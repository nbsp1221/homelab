import pytest

from homelab_infra.stacks import (
    StackAssets,
    load_stack_assets,
    render_environment_seed,
    select_stacks,
)


def test_compose_only_projects_do_not_upload_other_files(tmp_path) -> None:
    (tmp_path / ".env").write_text("secret")
    assert load_stack_assets(tmp_path) == StackAssets()


@pytest.mark.parametrize(
    "asset",
    [
        "../secret",
        "/secret",
        ".env",
        "config/.env",
        "data/id",
        "config/key.pem",
        "compose.yaml",
        "config/../secret",
    ],
)
def test_manifest_rejects_runtime_secrets_and_escaped_paths(tmp_path, asset) -> None:
    (tmp_path / "deploy.yaml").write_text(f"files: ['{asset}']\n")
    with pytest.raises(ValueError, match="Unsafe deployment asset"):
        load_stack_assets(tmp_path)


def test_manifest_rejects_symlinks(tmp_path) -> None:
    (tmp_path / "original").write_text("public")
    (tmp_path / "Dockerfile").symlink_to(tmp_path / "original")
    (tmp_path / "deploy.yaml").write_text("files: [Dockerfile]\n")
    with pytest.raises(ValueError, match="Symlink deployment asset"):
        load_stack_assets(tmp_path)


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
