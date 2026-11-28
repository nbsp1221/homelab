import os
import subprocess

import pytest

from tasks.swap import (
    build_swap_creation,
    canonical_fstab_entry,
    swap_size_bytes,
    validate_path,
)


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


def test_partial_swap_initialization_publishes_nothing_and_can_retry(tmp_path):
    mkswap = tmp_path / "mkswap"
    mkswap.write_text('#!/bin/sh\n[ "$FAIL_INITIALIZATION" != yes ]\n')
    mkswap.chmod(0o700)
    path = tmp_path / "swapfile"
    command = ["sh", "-ec", build_swap_creation(str(path), 1)]
    environment = {**os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}"}
    failed = subprocess.run(
        command, env={**environment, "FAIL_INITIALIZATION": "yes"}, check=False
    )
    assert failed.returncode != 0
    assert not path.exists()
    assert not list(tmp_path.glob("swapfile.homelab.*"))
    subprocess.run(command, env=environment, check=True)
    assert path.stat().st_size == 1024 * 1024
    assert path.stat().st_mode & 0o777 == 0o600
