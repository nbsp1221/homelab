import pytest

from group_data import all as all_data
from group_data import gcp as gcp_data
from group_data import oci as oci_data
from homelab_infra.hosts import REPO_ROOT, load_hosts
from inventories.production import gcp, oci


def test_production_inventory_contains_the_three_tailscale_hosts() -> None:
    assert gcp == ["retn0-srv-gcp-01"]
    assert oci == ["retn0-srv-oci-01", "retn0-srv-oci-02"]


def test_host_definitions_are_the_stack_placement_source() -> None:
    hosts = load_hosts()
    assert set(hosts) == {
        "retn0-srv-main",
        "retn0-srv-gcp-01",
        "retn0-srv-oci-01",
        "retn0-srv-oci-02",
    }
    assert hosts["retn0-srv-main"]["stacks"] == {}
    assert hosts["retn0-srv-gcp-01"]["stacks"]["beszel-agent"] == (
        {"env": {"BESZEL_HUB_URL": "https://beszel.retn0.dev"}}
    )
    assert hosts["retn0-srv-gcp-01"]["stacks"]["caddy-gcp"] == {
        "env": {
            "CADDY_DOMAIN": "beszel.retn0.dev",
            "CADDY_BIND_IPV4": "100.82.114.104",
            "CADDY_BIND_IPV6": "fd7a:115c:a1e0::7536:7269",
        }
    }
    for name in ("retn0-srv-oci-01", "retn0-srv-oci-02"):
        assert hosts[name]["stacks"] == {
            "beszel-agent": {"env": {"BESZEL_HUB_URL": "https://beszel.retn0.dev"}}
        }
    for config in hosts.values():
        for stack in config["stacks"]:
            assert (REPO_ROOT / "compose" / stack / "compose.yaml").is_file()


def test_host_definitions_reject_invalid_stack_paths(tmp_path) -> None:
    host_dir = tmp_path / "example"
    host_dir.mkdir()
    (host_dir / "host.yaml").write_text(
        "provider: gcp\nstacks:\n  ../other:\n    env: {}\n"
    )
    with pytest.raises(ValueError, match="Invalid stack name"):
        load_hosts(tmp_path)


def test_host_definitions_reject_invalid_environment_keys(tmp_path) -> None:
    host_dir = tmp_path / "example"
    host_dir.mkdir()
    (host_dir / "host.yaml").write_text(
        "provider: gcp\nstacks:\n  beszel-agent:\n"
        "    env:\n      'BESZEL_HUB_URL=bad': https://beszel.retn0.dev\n"
    )
    with pytest.raises(ValueError, match="Invalid environment"):
        load_hosts(tmp_path)


def test_group_data_expresses_shared_and_provider_specific_intent() -> None:
    assert all_data.ssh_key == "/home/retn0/.ssh/oci-main-bootstrap"
    assert all_data._sudo is True
    assert all_data.swap_path == "/swapfile"
    assert all_data.swap_size_mb == 2048

    assert gcp_data.ssh_user == "retn0"
    assert gcp_data.docker_users == ("retn0",)
    assert oci_data.ssh_user == "ubuntu"
    assert oci_data.docker_users == ("ubuntu",)
