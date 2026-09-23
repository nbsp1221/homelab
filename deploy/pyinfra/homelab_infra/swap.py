import re

from pyinfra import host
from pyinfra.api import deploy
from pyinfra.api.exceptions import DeployError
from pyinfra.facts.files import File, FindInFile
from pyinfra.facts.server import Command
from pyinfra.operations import files, server

from homelab_infra.package_state import command_lines


def validate_path(path: str) -> str:
    if path == "/" or not re.fullmatch(r"/[A-Za-z0-9._/-]+", path):
        raise ValueError("Swap path must be a simple absolute POSIX path")
    return path


def swap_size_bytes(size_mb: int) -> int:
    if size_mb <= 0:
        raise ValueError("Swap size must be positive")
    return size_mb * 1024 * 1024


def canonical_fstab_entry(path: str) -> str:
    return f"{validate_path(path)} none swap sw 0 0"


@deploy("Configure swap file")
def configure_swap() -> None:
    path = validate_path(host.data.swap_path)
    size_mb = host.data.swap_size_mb
    expected_bytes = swap_size_bytes(size_mb)
    swap_file = host.get_fact(File, path=path)

    if swap_file is False:
        raise DeployError(f"{path} exists but is not a regular file")
    if swap_file and swap_file["size"] != expected_bytes:
        raise DeployError(
            f"{path} is {swap_file['size']} bytes; expected {expected_bytes}"
        )

    if swap_file:
        signature = host.get_fact(
            Command,
            command=(
                "/usr/sbin/blkid --probe --match-tag TYPE --output value "
                f"{path} || true"
            ),
            _sudo=True,
        )
        if (signature or "").strip() != "swap":
            raise DeployError(f"{path} does not contain a swap signature")

    fstab_pattern = rf"^[[:space:]]*{re.escape(path)}[[:space:]]"
    fstab_lines = host.get_fact(
        FindInFile,
        path="/etc/fstab",
        pattern=fstab_pattern,
        extended_regex=True,
    )
    if fstab_lines and len(fstab_lines) > 1:
        raise DeployError(f"Multiple fstab entries exist for {path}")

    if not swap_file:
        server.shell(
            name="Allocate the swap file",
            commands=f"fallocate -l {size_mb}MiB {path}",
        )

    files.file(
        name="Secure the swap file",
        path=path,
        user="root",
        group="root",
        mode="0600",
    )

    if not swap_file:
        server.shell(
            name="Format the new swap file",
            commands=f"/sbin/mkswap {path}",
        )

    files.line(
        name="Persist the swap file",
        path="/etc/fstab",
        line=rf"^\s*{re.escape(path)}\s.*$",
        replace=canonical_fstab_entry(path),
        backup=True,
        ensure_newline=True,
        extended_regex=True,
    )

    active_swaps = command_lines(
        host.get_fact(
            Command,
            command="/sbin/swapon --show=NAME --noheadings --raw",
        )
    )
    if path not in active_swaps:
        server.shell(
            name="Activate the swap file",
            commands=f"/sbin/swapon {path}",
        )
