import fcntl
import json
import os
import shutil
import subprocess
import sys
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
import json
import os
import sys
from pathlib import Path

args = sys.argv[1:]
failure = os.environ["FAIL"]
running = Path(os.environ["RUNNING"])
log = Path(os.environ["DOCKER_LOG"])
if args[0] == "ps":
    if running.exists() or os.environ["FOREIGN_DIRECTORY"]:
        directory = os.environ["FOREIGN_DIRECTORY"] or os.environ["PROJECT_DIRECTORY"]
        print(f"fixture-id|{directory}|False")
    sys.exit(0)
assert args.pop(0) == "compose"
files = []
while args[0] in ("-f", "--env-file", "--project-directory"):
    option, value = args[:2]
    args = args[2:]
    if option == "-f":
        files.append(value)
    elif option == "--env-file":
        env_file = value
    else:
        project = value
path = Path(files[0])
version = path.read_text().strip()
operation = args[0]
with log.open("a") as stream:
    stream.write(json.dumps({
        "operation": operation,
        "files": files,
        "project": project,
        "env_file": env_file,
        "value": os.getenv("VALUE"),
        "path": os.getenv("PATH"),
    }) + "\\n")
if operation == "config":
    assert path.parent.name.startswith(".deploy-")
    assert "--format" in args
    if failure == "config":
        sys.exit(1)
    print(json.dumps({"name": "example-project"}, indent=2))
elif operation == "run":
    assert (path.parent / "config/Caddyfile").read_text() == "new config"
    assert args[args.index("--volume") + 1] == f"{path.parent}/config:/etc/caddy:ro"
    sys.exit(failure == "run")
elif operation == "up":
    assert "--wait" in args
    running.write_text(version)
    sys.exit(failure == "up")
elif operation == "exec":
    sys.exit(failure == "exec")
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
    (tmp_path / "compose-locks").mkdir(mode=0o555)
    docker = tools / "docker"
    docker.write_text(DOCKER)
    docker.chmod(0o700)
    sleep = tools / "sleep"
    sleep.write_text("#!/bin/sh\nexit 0\n")
    sleep.chmod(0o700)
    return project, stage, running, tools


def apply(stack_case, *, fail="", caddy="yes", foreign_directory="", value=""):
    project, stage, running, tools = stack_case
    return subprocess.run(
        [
            "sh",
            str(SCRIPT),
            str(project),
            str(stage),
            "yes",
            caddy,
            str(project.parent / "compose-locks"),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        env={
            **os.environ,
            "PATH": f"{tools}:{os.environ['PATH']}",
            "RUNNING": str(running),
            "DOCKER_LOG": str(project.parent / "docker.log"),
            "FAIL": fail,
            "PROJECT_DIRECTORY": str(project),
            "FOREIGN_DIRECTORY": str(foreign_directory),
            "VALUE": value,
        },
    )


def invocations(project):
    return [
        json.loads(line)
        for line in (project.parent / "docker.log").read_text().splitlines()
    ]


@pytest.mark.parametrize("failure", ["config", "run"])
def test_validation_failure_leaves_active_files_and_running_state(stack_case, failure):
    project, stage, running, _ = stack_case
    result = apply(stack_case, fail=failure)
    assert result.returncode != 0
    assert (project / "compose.yaml").read_text() == "old"
    assert (project / "config/Caddyfile").read_text() == "old config"
    assert (project / ".env").read_text() == OLD_ENV
    assert running.read_text() == "old"
    assert not stage.exists()


@pytest.mark.parametrize("failure", ["up", "exec"])
def test_failure_after_promotion_reports_failure_for_operator(stack_case, failure):
    project, stage, running, _ = stack_case
    result = apply(stack_case, fail=failure)
    assert result.returncode != 0
    assert "Inspect the project before retrying" in result.stderr
    assert (project / "compose.yaml").read_text() == "new"
    assert running.read_text() == "new"
    assert not stage.exists()
    assert [run["operation"] for run in invocations(project)].count("up") == 1


def test_same_project_in_another_directory_is_left_running(stack_case):
    project, stage, running, _ = stack_case
    (project / "compose.yaml").unlink()
    other = project.parent / "foreign"
    other.mkdir()
    result = apply(stack_case, foreign_directory=other)
    assert result.returncode != 0
    assert "already managed from another directory" in result.stderr
    assert not (project / "compose.yaml").exists()
    assert running.read_text() == "old"
    assert [run["operation"] for run in invocations(project)] == ["config"]
    assert not stage.exists()


def test_busy_read_only_host_lock_blocks_concurrent_promotion(stack_case):
    project, stage, running, _ = stack_case
    directory = project.parent / "compose-locks"
    lock = os.open(directory, os.O_RDONLY)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        result = apply(stack_case)
    finally:
        os.close(lock)
    assert result.returncode != 0
    assert "already running on this host" in result.stderr
    assert not (project.parent / "docker.log").exists()
    assert (project / "compose.yaml").read_text() == "old"
    assert running.read_text() == "old"
    assert not stage.exists()
    assert not list(directory.iterdir())


@pytest.mark.skipif(os.geteuid() == 0, reason="requires an unprivileged operator")
def test_manager_bootstrap_without_sudo_needs_no_writable_host_lock(stack_case):
    fixture, _, running, tools = stack_case
    root = fixture.parent
    home = root / "home"
    target = home / "compose/arcane"
    source = root / "stacks/arcane"
    source.mkdir(parents=True)
    (source / "compose.yaml").write_text("new")
    (source / ".env.example").touch()
    inventory = root / "manager.py"
    inventory.write_text(
        'manager = [("@local", {"stacks": {"arcane": {"bootstrap": True}}})]\n'
    )
    seed = root / "seed.env"
    seed.write_text("SECRET=fixture\n")
    seed.chmod(0o600)
    running.unlink()
    lock_directory = root / "compose-locks"
    launcher = """\
import os
import shlex
from pathlib import Path

from pyinfra.api import StringCommand
from pyinfra.facts.server import Home
from pyinfra_cli.main import main
from tasks import stacks

root = Path(os.environ["FIXTURE_ROOT"])
stacks.REPO_ROOT = root
stacks.COMPOSE_LOCK_DIRECTORY = str(root / "compose-locks")

# Redirect only the login's home so the real CLI cannot touch active stacks.
def fixture_home(self, user=""):
    return StringCommand("echo " + shlex.quote(str(root / "home")))

Home.command = fixture_home
main()
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            launcher,
            str(inventory),
            "tasks.stacks.apply",
            "--data",
            "_sudo=false",
            "--data",
            "stack=arcane",
            "--data",
            f"stack_env_file={seed}",
            "--serial",
            "--yes",
        ],
        cwd=SCRIPT.parents[1],
        env={
            **os.environ,
            "FIXTURE_ROOT": str(root),
            "PATH": f"{tools}:{os.environ['PATH']}",
            "RUNNING": str(running),
            "DOCKER_LOG": str(root / "docker.log"),
            "FAIL": "",
            "PROJECT_DIRECTORY": str(target),
            "FOREIGN_DIRECTORY": "",
        },
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (target / ".env").read_text() == seed.read_text()
    assert running.read_text() == "new"
    assert not list(lock_directory.iterdir())


def test_nonreplaceable_manifest_never_promotes_environment(stack_case):
    project, stage, running, _ = stack_case
    manifest = project / "compose.yaml"
    manifest.unlink()
    manifest.mkdir()
    (stage / "managed.env").write_text(
        '# BEGIN HOMELAB HOST VALUES\nVALUE="new"\n# END HOMELAB HOST VALUES\n'
    )
    result = apply(stack_case)
    assert result.returncode != 0
    assert "Compose cannot replace" in result.stderr
    assert (project / ".env").read_text() == OLD_ENV
    assert (project / "config/Caddyfile").read_text() == "old config"
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
def test_bootstrap_environment_seed_with_existing_manifest(stack_case, existing):
    project, stage, _, _ = stack_case
    if not existing:
        (project / ".env").unlink()
    (stage / "seed.env").write_text("SECRET=seed\n")
    result = apply(stack_case, caddy="no")
    assert result.returncode == 0, result.stderr
    assert (project / ".env").read_text() == (
        "SECRET=fixture\n" if existing else "SECRET=seed\n"
    )


@pytest.mark.parametrize(
    "filename", ["compose.override.yml", "docker-compose.override.yaml"]
)
def test_local_override_stops_before_docker_or_file_promotion(stack_case, filename):
    project, stage, running, _ = stack_case
    (project / filename).write_text("host-managed")
    result = apply(stack_case)
    assert result.returncode != 0
    assert f"Compose override {project / filename} is unsupported" in result.stderr
    assert not (project.parent / "docker.log").exists()
    assert (project / "compose.yaml").read_text() == "old"
    assert (project / ".env").read_text() == OLD_ENV
    assert (project / filename).read_text() == "host-managed"
    assert running.read_text() == "old"
    assert not stage.exists()


def test_managed_values_take_precedence_even_when_path_is_unset(stack_case):
    project, stage, _, _ = stack_case
    (stage / "managed.env").write_text(
        '# BEGIN HOMELAB HOST VALUES\nVALUE="inventory"\n'
        'PATH="/container/bin"\n# END HOMELAB HOST VALUES\n'
    )
    result = apply(stack_case, caddy="no", value="inherited")
    assert result.returncode == 0, result.stderr
    candidate, active = invocations(project)
    assert candidate["project"] == active["project"] == str(project)
    assert all(
        run["value"] is None and run["path"] is None for run in (candidate, active)
    )
    assert 'VALUE="inventory"' in (project / ".env").read_text()
    assert 'PATH="/container/bin"' in (project / ".env").read_text()


def test_fresh_caddy_config_directory_belongs_to_project_owner(stack_case):
    project, _, _, _ = stack_case
    shutil.rmtree(project / "config")
    result = apply(stack_case)
    assert result.returncode == 0, result.stderr
    config = (project / "config").stat()
    owner = project.stat()
    assert (config.st_uid, config.st_gid) == (owner.st_uid, owner.st_gid)
    assert config.st_mode & 0o777 == 0o700


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
    target, stage, requires_env, caddy, lock_directory = script.call_args.kwargs["args"]
    assert target == f"/srv/{owner}/compose/arcane-agent"
    assert stage.startswith(f"{target}/.deploy-")
    assert (requires_env, caddy) == ("yes", "no")
    assert all(
        call.kwargs["path"] != lock_directory for call in directory.call_args_list
    )
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
