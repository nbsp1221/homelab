import runpy
from pathlib import Path

import pytest

from homelab_infra import hosts


def write_host(root: Path, name: str, contents: str) -> None:
    host_dir = root / name
    host_dir.mkdir()
    (host_dir / "host.yaml").write_text(contents)


def test_cloud_inventory_groups_hosts_by_provider(tmp_path, monkeypatch) -> None:
    write_host(tmp_path, "cloud-a", "provider: gcp\nstacks: {}\n")
    write_host(tmp_path, "cloud-b", "provider: oci\nstacks: {}\n")
    write_host(tmp_path, "local-a", "provider: local\nstacks: {}\n")
    definitions = hosts.load_hosts(tmp_path)
    monkeypatch.setattr(hosts, "load_hosts", lambda: definitions)

    inventory = runpy.run_path(
        str(Path(__file__).parents[1] / "inventories/production.py")
    )

    assert inventory["gcp"] == ["cloud-a"]
    assert inventory["oci"] == ["cloud-b"]


def test_host_definitions_preserve_stack_settings(tmp_path) -> None:
    write_host(
        tmp_path,
        "cloud-a",
        "provider: oci\nstacks:\n"
        "  bootstrap-agent:\n    bootstrap: true\n"
        "    env:\n      CONTROLLER_URL: https://controller.example\n"
        "  example-app: {}\n",
    )

    assert hosts.load_hosts(tmp_path)["cloud-a"]["stacks"] == {
        "bootstrap-agent": {
            "bootstrap": True,
            "env": {"CONTROLLER_URL": "https://controller.example"},
        },
        "example-app": {},
    }


def test_host_definitions_reject_invalid_stack_paths(tmp_path) -> None:
    write_host(
        tmp_path, "cloud-a", "provider: gcp\nstacks:\n  ../other:\n    env: {}\n"
    )
    with pytest.raises(ValueError, match="Invalid stack name"):
        hosts.load_hosts(tmp_path)


def test_host_definitions_reject_invalid_environment_keys(tmp_path) -> None:
    write_host(
        tmp_path,
        "cloud-a",
        "provider: gcp\nstacks:\n  example-app:\n"
        "    env:\n      'ENDPOINT=bad': https://service.example\n",
    )
    with pytest.raises(ValueError, match="Invalid environment"):
        hosts.load_hosts(tmp_path)
