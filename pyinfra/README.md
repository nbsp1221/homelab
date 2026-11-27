# pyinfra

This executor applies the selected configuration to managed Linux hosts. Run pyinfra from a controller with OpenSSH access to the targets over Tailscale. Managed hosts do not run an agent or require Python.

## Scope

- Audit existing Debian and Ubuntu hosts.
- Install the small package set required by the baseline.
- Maintain a 2 GiB disk-backed swap file.
- Install current Docker Engine and Docker Compose from Docker's official
  repository.
- Manage the GCP host's systemd-resolved/Tailscale DNS integration through a dedicated, IAP-guarded deployment with local rollback and DNS verification.
- Run Docker upgrades and operating-system maintenance on explicit request.

Provision cloud resources, enroll Tailscale, and manage firewalls and secrets through their respective tools.

## Controller setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on the controller, then synchronize the locked Python 3.12 environment from the repository root:

```bash
cd pyinfra
uv sync --locked
```

uv selects Python from `.python-version`, creates `.venv`, and installs the
exact dependency graph recorded in `uv.lock`. The virtual environment is local
runtime state and must not be committed.

## Validation

Run commands from this directory:

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run python -m compileall -q deploy.py inventory.py group_data tasks tests
uv run pyinfra inventory.py debug-inventory
```

## Operation

The public inventory names the targets and records their desired configuration. Configure each alias in the controller's `~/.ssh/config` and independently verify the corresponding host key in `known_hosts`. Example:

```sshconfig
Host gcp-01
    HostName cloud.example.net
    User operator
    IdentityFile ~/.ssh/example-operator
    StrictHostKeyChecking yes
```

An SSH agent can supply the identity instead of an identity file. Verify the alias with both `ssh` and pyinfra's read-only `server.Hostname` fact. The inventory enforces strict host-key checking.

Keep site-specific settings in a private group-data directory on the controller. Use the inventory's group names as filenames. For example, `gcp.py` supplies DNS probes, and `gcp.py`, `oci.py`, or `mini.py` can declare `docker_users = ("operator",)` for their group. Docker group membership grants root-level privileges.

Replace `gcp-01` in the examples with the inventory alias. Supply the controller's private group-data directory when targeting operational settings:

```bash
group_data="$HOME/.config/homelab/group_data"
uv run pyinfra --group-data "$group_data" inventory.py debug-inventory
```

Audit without changing host configuration:

```bash
uv run pyinfra --group-data "$group_data" inventory.py tasks.audit.run \
  --limit gcp-01 --serial --yes
```

Use `--limit cloud` to select the cloud hosts or a host alias to select just one. The baseline applies only to members of the `cloud` group.

```bash
uv run pyinfra --group-data "$group_data" inventory.py deploy.py \
  --limit gcp-01 --dry --diff --serial
```

Apply the baseline.

```bash
uv run pyinfra --group-data "$group_data" inventory.py deploy.py \
  --limit gcp-01 --serial --yes
```

Upgrade installed Docker packages or run general OS package maintenance:

```bash
uv run pyinfra --group-data "$group_data" inventory.py tasks.docker.upgrade \
  --limit gcp-01 --serial --dry
uv run pyinfra --group-data "$group_data" inventory.py tasks.maintenance.run \
  --limit gcp-01 --serial --yes
```

GCP DNS changes are a separate [IAP-guarded procedure](DNS.md). The baseline applies prerequisites, swap, and Docker installation.

### Preview Docker on the mini server

Load the client key in the controller's SSH agent or select it in the alias's SSH configuration.

```bash
uv run --locked pyinfra --group-data "$group_data" inventory.py tasks.docker.install \
  --limit mini --dry
```

On hosts with password-protected sudo, add `--data _sudo=false` to plan using unprivileged facts. Use this override only for a preview. The Docker install task configures the repository and service and ensures the package set is present. Use `tasks.docker.upgrade` to refresh metadata and upgrade installed, unheld Docker packages. General package maintenance can also upgrade Docker during an explicit OS upgrade. Docker install applies strict APT refresh behavior to its own invocation. A drop-in created by an earlier release remains under the operator's control.

Deploy and recover [Caddy](../compose/caddy-gcp/README.md), [Arcane Manager](../stacks/arcane/README.md), and [Arcane Agent](../stacks/arcane-agent/README.md) through their Docker Compose procedures. Use [Arcane Git Pull](../arcane/syncs/README.md) for routine application updates.

## Project layout

- `inventory.py` defines the hosts and groups. `cloud` combines GCP and OCI, and `mini` selects the mini server.
- `group_data/` holds common policy defaults. The controller supplies private group data and SSH settings.
- `deploy.py` composes the baseline. Run a single task by its dotted name.
- `tasks/` holds the reusable Python implementation and its helpers.
- `tests/`: local tests for inventory, safety, and generated commands.

## Updating controller dependencies

Change version constraints in `pyproject.toml`, then deliberately refresh and
verify the lockfile:

```bash
uv lock --upgrade
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

Commit `pyproject.toml` and `uv.lock` together.
