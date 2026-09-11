import pytest

from homelab_infra.swap import canonical_fstab_entry, swap_size_bytes, validate_path


def test_swap_helpers_express_the_exact_baseline() -> None:
    assert swap_size_bytes(2048) == 2_147_483_648
    assert canonical_fstab_entry("/swapfile") == "/swapfile none swap sw 0 0"


@pytest.mark.parametrize("path", ["swapfile", "/swap file", "/swap;file", "/"])
def test_unsafe_swap_paths_are_rejected(path: str) -> None:
    with pytest.raises(ValueError, match="absolute POSIX path"):
        validate_path(path)


def test_non_positive_swap_size_is_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        swap_size_bytes(0)
