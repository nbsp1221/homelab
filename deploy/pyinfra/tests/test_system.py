import pytest

from homelab_infra.system import require_supported_distribution


@pytest.mark.parametrize("distribution", ["Debian", "Ubuntu"])
def test_supported_distributions_are_accepted(distribution: str) -> None:
    require_supported_distribution(distribution)


def test_unsupported_distribution_is_rejected() -> None:
    with pytest.raises(ValueError, match="Debian and Ubuntu"):
        require_supported_distribution("Fedora")
