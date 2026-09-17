from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.server import LinuxDistribution
from pyinfra.operations import apt

BASE_PACKAGES = ("ca-certificates", "curl")
SUPPORTED_DISTRIBUTIONS = frozenset({"Debian", "Ubuntu"})


def require_supported_distribution(distribution: str) -> None:
    if distribution not in SUPPORTED_DISTRIBUTIONS:
        raise ValueError("The baseline supports Debian and Ubuntu only")


@deploy("Configure baseline packages")
def configure_system() -> None:
    distribution = host.get_fact(LinuxDistribution)["name"]
    try:
        require_supported_distribution(distribution)
    except ValueError as error:
        raise DeployError(str(error)) from error

    apt.packages(
        name="Install baseline prerequisite packages",
        packages=list(BASE_PACKAGES),
        update=True,
        cache_time=3600,
    )
