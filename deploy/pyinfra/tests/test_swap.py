import pytest

from homelab_infra.swap import canonical_fstab_entry, swap_size_bytes, validate_path


def test_swap_size_converts_mebibytes_to_bytes() -> None:
    assert swap_size_bytes(3) == 3_145_728


def test_fstab_entry_uses_the_selected_swap_path() -> None:
    assert canonical_fstab_entry("/var/swap/example") == (
        "/var/swap/example none swap sw 0 0"
    )


@pytest.mark.parametrize("path", ["swapfile", "/swap file", "/swap;file", "/"])
def test_unsafe_swap_paths_are_rejected(path: str) -> None:
    with pytest.raises(ValueError, match="absolute POSIX path"):
        validate_path(path)


def test_non_positive_swap_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        swap_size_bytes(0)
