from group_data import all as all_data
from group_data import gcp as gcp_data
from group_data import oci as oci_data
from inventories.production import gcp, oci


def test_production_inventory_contains_the_three_tailscale_hosts() -> None:
    assert gcp == ["retn0-srv-gcp-01"]
    assert oci == ["retn0-srv-oci-01", "retn0-srv-oci-02"]


def test_group_data_expresses_shared_and_provider_specific_intent() -> None:
    assert all_data.ssh_key == "/home/retn0/.ssh/oci-main-bootstrap"
    assert all_data._sudo is True
    assert all_data.swap_path == "/swapfile"
    assert all_data.swap_size_mb == 2048

    assert gcp_data.ssh_user == "retn0"
    assert gcp_data.docker_users == ("retn0",)
    assert oci_data.ssh_user == "ubuntu"
    assert oci_data.docker_users == ("ubuntu",)
