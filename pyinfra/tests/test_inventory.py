import json
import subprocess
import sys
from pathlib import Path


def test_inventory_resolves_group_defaults_and_host_overrides(
    tmp_path,
) -> None:
    controller = tmp_path / "controller"
    group_data = controller / "group_data"
    group_data.mkdir(parents=True)
    (group_data / "all.py").write_text("_sudo = True\n")
    (group_data / "cloud.py").write_text("swap_size_mb = 2048\n")
    inventory = tmp_path / "private.py"
    inventory.write_text('cloud = [("cloud.example", {"swap_size_mb": 4096})]\n')
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("pyinfra")),
            str(inventory),
            "debug-inventory",
        ],
        cwd=controller,
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout + result.stderr
    assert "[cloud.example]" in output
    host_data = json.JSONDecoder().raw_decode(output[output.index("{") :])[0]
    assert host_data["_sudo"] is True
    assert host_data["swap_size_mb"] == 4096


def test_private_group_data_supplies_host_configuration(tmp_path):
    inventory = tmp_path / "inventory.py"
    inventory.write_text('gcp = ["cloud.example"]\n')
    private = tmp_path / "site"
    private.mkdir()
    (private / "gcp.py").write_text(
        'dns_probe_names = ("dns.example",)\ndocker_users = ("docker-operator",)\n'
    )
    result = subprocess.run(
        [
            str(Path(sys.executable).with_name("pyinfra")),
            "--group-data",
            str(private),
            str(inventory),
            "debug-inventory",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    output = result.stdout + result.stderr
    data = json.JSONDecoder().raw_decode(output[output.index("{") :])[0]
    assert data["dns_probe_names"] == ["dns.example"]
    assert data["docker_users"] == ["docker-operator"]
    assert "ssh_user" not in data and "ssh_key" not in data
