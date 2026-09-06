from collections.abc import Iterable


def command_lines(output: str | None) -> tuple[str, ...]:
    return tuple((output or "").splitlines())


def _apt_names(output: str | None, *, repository_suffix: bool) -> set[str]:
    names: set[str] = set()
    for line in command_lines(output):
        token = line.strip().split(maxsplit=1)[0] if line.strip() else ""
        if repository_suffix:
            token = token.split("/", 1)[0]
        token = token.split(":", 1)[0]
        if token and token != "Listing...":
            names.add(token)
    return names


def packages_need_upgrade(
    upgradable_output: str | None,
    held_output: str | None,
    package_names: Iterable[str],
) -> bool:
    managed = set(package_names)
    upgradable = _apt_names(upgradable_output, repository_suffix=True)
    held = _apt_names(held_output, repository_suffix=False)
    return bool((managed & upgradable) - held)
