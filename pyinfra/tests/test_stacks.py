import fcntl
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tasks import stacks

SCRIPT = Path(__file__).parents[1] / "files/apply_stack.sh"
OLD_ENV = (
    "SECRET=fixture\n"
    "# BEGIN HOMELAB HOST VALUES\nOLD=outdated\n"
    "# END HOMELAB HOST VALUES\n"
)
DOCKER = """\
#!/usr/bin/env python3
import os
import sys
from pathlib import Path

args = sys.argv
path = Path(args[args.index("-f") + 1])
version = path.read_text().strip()
operation = args[args.index("-f") + 2]
failure = os.environ["FAIL"]
running = Path(os.environ["RUNNING"])
if operation == "ps":
    if running.exists():
        print(running.read_text())
elif operation in ("config", "run"):
    assert path.parent.name.startswith(".deploy-")
    assert "--env-file" in args
    if operation == "run":
        assert (path.parent / "config/Caddyfile").read_text() == "new config"
    sys.exit(failure == operation)
elif operation == "up":
    assert "--wait" in args
    running.write_text(version)
    if version == "new" and failure in ("up", "rollback"):
        sys.exit(1)
    if version == "old" and failure == "rollback":
        sys.exit(1)
elif operation == "exec":
    sys.exit(failure == "exec" and version == "new")
elif operation == "stop":
    running.unlink(missing_ok=True)
else:
    sys.exit(99)
"""


@pytest.fixture
def stack_case(tmp_path):
    project = tmp_path / "example-project"
    stage = project / ".deploy-example"
    (stage / "config").mkdir(parents=True)
    (stage / "compose.yaml").write_text("new")
    (stage / "config/Caddyfile").write_text("new config")
    (project / "config").mkdir()
    (project / "config/Caddyfile").write_text("old config")
    (project / "compose.yaml").write_text("old")
    (project / ".env").write_text(OLD_ENV)
    (project / ".env").chmod(0o600)
    running = tmp_path / "running"
    running.write_text("old")
    tools = tmp_path / "bin"
    tools.mkdir()
    docker = tools / "docker"
    docker.write_text(DOCKER)
    docker.chmod(0o700)
    sleep = tools / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o700)
    return project, stage, running, tools


def apply(stack_case, *, fail="", caddy="yes"):
    project, stage, running, tools = stack_case
    return subprocess.run(
        ["sh", str(SCRIPT), str(project), str(stage), "yes", caddy],
        capture_output=True,
        text=True,
        timeout=10,
        env={
            **os.environ,
            "PATH": f"{tools}:{os.environ['PATH']}",
            "RUNNING": str(running),
            "FAIL": fail,
        },
    )


@pytest.mark.parametrize("failure", ["config", "run", "up", "exec"])
def test_failure_preserves_previous_project_files_and_running_state(
    stack_case, failure
):
    project, stage, running, _ = stack_case
    result = apply(stack_case, fail=failure)
    assert result.returncode != 0
    assert (project / "compose.yaml").read_text() == "old"
    assert (project / "config/Caddyfile").read_text() == "old config"
    assert (project / ".env").read_text() == OLD_ENV
    assert running.read_text() == "old"
    assert not stage.exists()
    if failure in ("up", "exec"):
        assert "Previous files and running state restored" in result.stderr


@pytest.mark.parametrize("has_previous_manifest", [False, True])
def test_failed_apply_keeps_initially_stopped_project_stopped(
    stack_case, has_previous_manifest
):
    project, stage, running, _ = stack_case
    if not has_previous_manifest:
        (project / "compose.yaml").unlink()
    running.unlink()
    result = apply(stack_case, fail="up", caddy="no")
    assert result.returncode != 0
    assert (project / "compose.yaml").exists() is has_previous_manifest
    assert (project / ".env").read_text() == OLD_ENV
    assert not running.exists()
    assert not stage.exists()


def test_failed_rollback_retains_recovery_directory(stack_case):
    project, stage, _, _ = stack_case
    result = apply(stack_case, fail="rollback")
    assert result.returncode != 0
    assert "Compose rollback failed" in result.stderr
    assert str(stage) in result.stderr
    assert stage.exists()
    assert (project / "compose.yaml").read_text() == "old"
    assert (stage / "previous/compose").read_text() == "old"


def test_busy_lock_prevents_concurrent_promotion(stack_case):
    project, stage, running, _ = stack_case
    with (project / ".deploy.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = apply(stack_case)
    assert result.returncode != 0
    assert "already running" in result.stderr
    assert (project / "compose.yaml").read_text() == "old"
    assert running.read_text() == "old"
    assert not stage.exists()


def test_success_clears_managed_block_and_preserves_secrets(stack_case):
    project, stage, running, _ = stack_case
    result = apply(stack_case)
    assert result.returncode == 0, result.stderr
    assert (project / "compose.yaml").read_text() == "new"
    assert (project / "config/Caddyfile").read_text() == "new config"
    assert (project / ".env").read_text() == "SECRET=fixture\n"
    assert (project / ".env").stat().st_mode & 0o777 == 0o600
    assert running.read_text() == "new"
    assert not stage.exists()


@pytest.mark.parametrize("existing", [False, True])
def test_bootstrap_environment_seed_is_used_only_if_missing(stack_case, existing):
    project, stage, _, _ = stack_case
    if not existing:
        (project / ".env").unlink()
    (stage / "seed.env").write_text("SECRET=seed\n")
    result = apply(stack_case, caddy="no")
    assert result.returncode == 0, result.stderr
    assert (project / ".env").read_text() == (
        "SECRET=fixture\n" if existing else "SECRET=seed\n"
    )


def test_managed_environment_round_trips_through_compose(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker CLI is required")
    check = subprocess.run(["docker", "compose", "version"], capture_output=True)
    if check.returncode:
        pytest.skip("Docker Compose plugin is required")
    value = '${AUDIT_UNSET:-different} \\trailing\\ "quote" café\tvalue'
    (tmp_path / ".env").write_text(stacks.render_managed_env({"CHECK": value}))
    (tmp_path / "compose.yaml").write_text(
        "services:\n  sample:\n    image: example.invalid/sample:1\n"
        '    environment:\n      SAMPLE: "${CHECK:?}"\n'
    )
    parsed = subprocess.run(
        ["docker", "compose", "config", "--environment"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"CHECK={value}" in parsed.stdout.splitlines()


@pytest.mark.parametrize(
    ("assignments", "error"),
    [
        ({"../outside": {}}, "Invalid stack name"),
        ({"caddy-gcp": {"env": {"X=bad": "fixture"}}}, "Invalid environment"),
        ({"caddy-gcp": {"env": {"X": "line\nbreak"}}}, "Invalid environment"),
    ],
)
def test_invalid_assignments_are_rejected(assignments, error):
    with pytest.raises(ValueError, match=error):
        stacks.select_stacks(assignments, "caddy-gcp")


@pytest.mark.parametrize("selected", [None, "unassigned-app"])
def test_task_requires_explicit_infrastructure_stack(monkeypatch, selected):
    uploads = Mock()
    monkeypatch.setattr(stacks, "host", SimpleNamespace(data={"stack": selected}))
    monkeypatch.setattr(stacks.files, "put", uploads)
    with pytest.raises(ValueError, match="Select an infrastructure stack"):
        stacks.apply._inner()
    uploads.assert_not_called()


@pytest.mark.parametrize("explicit_owner", [None, "stack-service"])
def test_task_stages_only_declared_assets_and_uses_owner_home(
    tmp_path, monkeypatch, explicit_owner
):
    source = tmp_path / "stacks/arcane-agent"
    source.mkdir(parents=True)
    (source / "compose.yaml").touch()
    (source / ".env.example").touch()
    (source / "unspecified.txt").touch()
    monkeypatch.setattr(stacks, "REPO_ROOT", tmp_path)
    owner = explicit_owner or "operator"
    data = {"stack": "arcane-agent", "stacks": {"arcane-agent": {"bootstrap": True}}}
    if explicit_owner:
        data["stack_owner"] = explicit_owner

    def get_fact(fact, *, _sudo, command=None, user=None):
        assert _sudo is False
        if fact is stacks.Home:
            assert user == owner
            return f"/srv/{owner}"
        assert fact is stacks.Command
        if command == "id -un":
            return "operator"
        assert command == f"id -gn -- {owner}"
        return "project-files"

    monkeypatch.setattr(stacks, "host", SimpleNamespace(data=data, get_fact=get_fact))
    directory, put, script = Mock(), Mock(), Mock()
    monkeypatch.setattr(stacks.files, "directory", directory)
    monkeypatch.setattr(stacks.files, "put", put)
    monkeypatch.setattr(stacks.server, "script", script)
    stacks.apply._inner()
    target, stage, requires_env, caddy = script.call_args.kwargs["args"]
    assert target == f"/srv/{owner}/compose/arcane-agent"
    assert stage.startswith(f"{target}/.deploy-")
    assert (requires_env, caddy) == ("yes", "no")
    target_directory = directory.call_args_list[0].kwargs
    assert (target_directory["user"], target_directory["group"]) == (
        owner,
        "project-files",
    )
    assert target_directory["_sudo"] is (explicit_owner is not None)
    assert {call.kwargs["dest"] for call in put.call_args_list} == {
        f"{stage}/compose.yaml",
        f"{stage}/managed.env",
    }
