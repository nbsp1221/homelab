import pytest

from homelab_infra.system import BASE_PACKAGES, require_supported_distribution


def test_system_baseline_has_only_runtime_prerequisites() -> None:
    assert BASE_PACKAGES == ("ca-certificates", "curl")


@pytest.mark.parametrize("distribution", ["Debian", "Ubuntu"])
def test_supported_distributions_are_accepted(distribution: str) -> None:
    require_supported_distribution(distribution)


def test_unsupported_distribution_is_rejected() -> None:
    with pytest.raises(ValueError, match="Debian and Ubuntu"):
        require_supported_distribution("Fedora")
