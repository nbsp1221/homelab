# pyinfra

This executor manages the baseline configuration and explicitly selected Compose stacks on managed Linux hosts. Run pyinfra from a controller with OpenSSH access to the targets over Tailscale. Managed hosts do not run an agent or require Python.

## Scope

- Audit existing Debian and Ubuntu hosts.
- Install the small package set required by the baseline.
- Maintain a 2 GiB disk-backed swap file.
- Install current Docker Engine and Docker Compose from Docker's official
  repository.
- Manage the GCP host's systemd-resolved/Tailscale DNS integration through a dedicated, IAP-guarded deployment with local rollback and DNS verification.
- Run operating-system package upgrades only when explicitly requested.
- Bootstrap Arcane and apply explicitly assigned infrastructure stacks using inventory host data.

Cloud resources, Tailscale enrollment, firewalls, and secret generation are outside this executor. Initial stack provisioning can explicitly seed an operator-provided private environment file; normal deployments preserve host-local secrets. The OS baseline does not automatically deploy application stacks.

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
uv run python -m compileall -q deploy.py group_data inventories tasks tests
uv run pyinfra inventories/cloud.py debug-inventory
uv run pyinfra inventories/mini.py debug-inventory
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

Keep site-specific settings in a private group-data directory on the controller. Use the inventory's group names as filenames. `gcp.py` supplies DNS probes and optional Docker group members, `oci.py` and `mini.py` may supply their own Docker group members, and `gcp_ingress.py` supplies the Caddy domain and listener addresses. For example:

```python
# gcp_ingress.py
stacks = {
    "caddy-gcp": {
        "env": {
            "CADDY_DOMAIN": "monitor.example.net",
            "CADDY_BIND_IPV4": "192.0.2.10",
            "CADDY_BIND_IPV6": "2001:db8::10",
        },
    },
}
```

Use `docker_users = ("operator",)` only for accounts that should have Docker daemon access. Docker group membership grants root-level privileges. The stack owner defaults to the authenticated account and its primary group. Set `stack_owner` in private host or group data to select another existing account. Bootstrap under a different owner requires sudo.

Replace `gcp-01` in the examples with the inventory alias. Supply the controller's private group-data directory when targeting operational settings:

```bash
group_data="$HOME/.config/homelab/group_data"
uv run pyinfra --group-data "$group_data" inventories/cloud.py debug-inventory \
  --limit gcp-01
```

Audit without changing host configuration:

```bash
uv run pyinfra --group-data "$group_data" inventories/cloud.py tasks.audit.run \
  --limit gcp-01 --serial --yes
```

Preview the baseline against one host:

```bash
uv run pyinfra --group-data "$group_data" inventories/cloud.py deploy.py \
  --limit gcp-01 --dry --diff --serial
```

Apply and verify the baseline:

```bash
uv run pyinfra --group-data "$group_data" inventories/cloud.py deploy.py \
  --limit gcp-01 --serial --yes
uv run pyinfra --group-data "$group_data" inventories/cloud.py tasks.verification.verify \
  --limit gcp-01 --serial --yes
```

Upgrade installed Docker packages or run general OS package maintenance:

```bash
uv run pyinfra --group-data "$group_data" inventories/cloud.py tasks.docker.upgrade \
  --limit gcp-01 --serial --dry
uv run pyinfra --group-data "$group_data" inventories/cloud.py tasks.maintenance.run \
  --limit gcp-01 --serial --yes
```

GCP DNS changes are a separate [IAP-guarded procedure](DNS.md). The baseline applies prerequisites, swap, and Docker installation. DNS and monitoring checks remain independently runnable.

### Preview Docker on the mini server

Load the client key in the controller's SSH agent or select it in the alias's SSH configuration.

```bash
uv run --locked pyinfra --group-data "$group_data" inventories/mini.py \
  tasks.docker.install --dry
```

On hosts with password-protected sudo, add `--data _sudo=false` to plan using unprivileged facts. Use this override only for a preview. The Docker install task configures the repository and service and ensures the package set is present. Use `tasks.docker.upgrade` to refresh metadata and upgrade installed, unheld Docker packages. General package maintenance can also upgrade Docker during an explicit OS upgrade. Docker install applies strict APT refresh behavior to its own invocation. A drop-in created by an earlier release remains under the operator's control.

### Compose stacks

Select the infrastructure project and host explicitly. Arcane owns routine application updates. The pyinfra task handles the Manager, Agent, and GCP Caddy.

```bash
uv run pyinfra --group-data "$group_data" inventories/cloud.py tasks.stacks.apply \
  --limit gcp-01 --data stack=caddy-gcp --dry --serial
uv run pyinfra --group-data "$group_data" inventories/cloud.py tasks.stacks.apply \
  --limit gcp-01 --data stack=caddy-gcp --serial --yes
```

Bootstrap stacks use the stack owner's `~/compose/<project>`. See the [Manager](../stacks/arcane/README.md#bootstrap-with-pyinfra) and [Agent](../stacks/arcane-agent/README.md#bootstrap-with-pyinfra) procedures. For private assignments, pass the absolute path to a private Python inventory in place of `inventories/cloud.py`. Groups such as `gcp` or `oci` still pick up their matching defaults. Migrate prior `HOMELAB_HOSTS_DIR` entries by copying their `stacks` map into the associated host's inventory data. Keep SSH credentials outside Git.

Each run stages its own Compose and configuration files with private permissions and acquires a per-project lock. It validates the candidate, replaces the active files, and waits up to 120 seconds for Compose startup. Caddy additionally validates its staged config and reloads after startup. On an ordinary command failure or handled signal after promotion, it restores prior files and reconciles the previous running or stopped project. Volumes and networks are left in place. If rollback itself fails, the operation reports the recovery directory. A host crash or uncatchable termination can still require manual recovery.

The task preserves host-local secrets and rewrites only its managed environment block, removing that block when the inventory values are cleared. A private `--data stack_env_file=/absolute/path/to/private.env` can provide the initial secret file if the target has none. Keep it at mode `0600` and omit `--diff` when passing it. Deploy [GCP Caddy](../compose/caddy-gcp/README.md) before adopting the [Beszel Hub](../stacks/beszel-hub/README.md). Use `tasks.monitoring.verify` to check both endpoints.

## Project layout

- `inventories/` contains the cloud and mini targets with any host-specific data.
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
