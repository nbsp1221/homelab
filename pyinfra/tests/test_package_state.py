from homelab_infra.package_state import command_lines, packages_need_upgrade


def test_empty_command_fact_has_no_lines() -> None:
    assert command_lines(None) == ()
    assert command_lines("") == ()
    assert command_lines("/swapfile\n") == ("/swapfile",)


def test_only_upgradeable_managed_packages_require_latest_operation() -> None:
    upgradable = """\
docker-ce/bookworm 2 amd64 [upgradable from: 1]
curl/bookworm 3 amd64 [upgradable from: 2]
"""

    assert packages_need_upgrade(
        upgradable,
        None,
        ("docker-ce", "docker-ce-cli"),
    )
    assert not packages_need_upgrade(upgradable, None, ("docker-ce-cli",))


def test_held_managed_packages_do_not_force_an_upgrade() -> None:
    upgradable = "docker-ce/bookworm 2 amd64 [upgradable from: 1]\n"

    assert not packages_need_upgrade(
        upgradable,
        "docker-ce\n",
        ("docker-ce", "missing"),
    )
