from homelab_infra.verification import build_baseline_verification


def test_final_verification_covers_the_complete_baseline_contract() -> None:
    command = build_baseline_verification("/swapfile", 2048, ("retn0",))

    assert "2147483648" in command
    assert "swapon" in command
    assert "/etc/apt/sources.list.d/docker.sources" in command
    assert "systemctl is-active --quiet docker" in command
    assert "systemctl is-enabled --quiet docker" in command
    assert "docker compose version --short" in command
    assert "id -nG -- retn0" in command


def test_operator_names_are_shell_quoted() -> None:
    command = build_baseline_verification("/swapfile", 2048, ("user name",))

    assert "id -nG -- 'user name'" in command
