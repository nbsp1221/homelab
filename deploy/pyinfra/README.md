# pyinfra

This executor manages the baseline configuration and explicitly selected Compose stacks on the homelab's cloud Linux hosts. pyinfra runs from `retn0-srv-main` and connects to managed hosts over Tailscale SSH. Managed hosts do not run an agent or require Python.

## Scope

- Audit existing Debian and Ubuntu hosts.
- Install the small package set required by the baseline.
- Maintain a 2 GiB disk-backed swap file.
- Install current Docker Engine and Docker Compose from Docker's official
  repository.
- Configure Docker startup to wait for the declared Tailscale listeners on hosts running `caddy-gcp`.
- Run operating-system package upgrades only when explicitly requested.
- Copy and apply Compose stacks listed in `hosts/<hostname>/host.yaml` when the stack deploy is explicitly requested.

Cloud resources, Tailscale enrollment, firewalls, and secret generation are outside this executor. Initial stack provisioning can explicitly seed an operator-provided private environment file; normal deployments preserve host-local secrets. The OS baseline does not automatically deploy application stacks.

## Controller setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on `retn0-srv-main`, then synchronize the locked Python 3.12 environment from the repository root:

```bash
cd deploy/pyinfra
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
uv run python -m compileall -q deploys group_data homelab_infra inventories tests
uv run pyinfra inventories/production.py debug-inventory
```

## Operation

Inspect the resolved data for one provider or host:

```bash
uv run pyinfra inventories/production.py debug-inventory --limit gcp
uv run pyinfra inventories/production.py debug-inventory \
  --limit retn0-srv-gcp-01
```

Audit without changing host configuration:

```bash
uv run pyinfra inventories/production.py deploys/audit.py \
  --limit retn0-srv-gcp-01 --serial --yes
```

Preview the baseline against one host:

```bash
uv run pyinfra inventories/production.py deploys/baseline.py \
  --limit retn0-srv-gcp-01 --dry --diff --serial
```

Apply and verify the baseline:

```bash
uv run pyinfra inventories/production.py deploys/baseline.py \
  --limit retn0-srv-gcp-01 --serial --yes
uv run pyinfra inventories/production.py deploys/verify.py \
  --limit retn0-srv-gcp-01 --serial --yes
```

Apply explicit package maintenance:

```bash
uv run pyinfra inventories/production.py deploys/maintenance.py \
  --limit retn0-srv-gcp-01 --serial --yes
```

### Docker startup on the GCP monitoring host

Docker binds Caddy's published host ports before Caddy starts. The ordinary `network-online.target` and `After=tailscaled.service` do not guarantee that Tailscale addresses exist yet, so a container healthcheck or Compose `depends_on` cannot fix this boot race.

The baseline installs `/etc/systemd/system/docker.service.d/10-homelab-tailscale.conf` before managing Docker packages or starting Docker. Hosts assigned `caddy-gcp` opt in through their existing stack placement; its `CADDY_BIND_IPV4` and `CADDY_BIND_IPV6` values are the only address source. Other hosts do not acquire this dependency. Removing that placement removes only this executor's drop-in, without deleting stacks or other Docker configuration.

The drop-in runs the official [`tailscale wait --timeout=60s`](https://tailscale.com/docs/reference/tailscale-cli#wait) in Docker's `ExecStartPre`, followed by checks that both declared addresses exist on `tailscale0` and are neither tentative nor DAD-failed. [Tailscale 1.102.3's implementation](https://github.com/tailscale/tailscale/blob/v1.102.3/cmd/tailscale/cli/wait.go) checks only the first assigned IP, so both interface checks are necessary. Every Docker activation, including socket activation, goes through these checks before restoring containers. Tailscale enrollment remains outside this executor; a missing `wait` command, daemon unit, or required utility stops planning before the drop-in is written.

An unsuccessful pre-start check prevents `dockerd` from starting. [`Restart=always`](https://www.freedesktop.org/software/systemd/man/systemd.service.html#Restart=) retries after 10 seconds, with start-rate limiting disabled so repeated early failures do not exhaust Docker's default three-attempt limit. Each readiness wait is capped at 60 seconds; there is no overall retry deadline. **All Docker containers on this host wait while Tailscale is unavailable or a declared address is incorrect.** The checks establish local address readiness, not DNS, peer connectivity, or application health. Existing Docker container restart policies remain responsible for restoring the applications.

For an existing host, preview and apply just this configuration without package upgrades, stack deployment, or Docker restart:

```bash
uv run pyinfra inventories/production.py deploys/docker_startup.py \
  --limit retn0-srv-gcp-01 --dry --diff --serial
uv run pyinfra inventories/production.py deploys/docker_startup.py \
  --limit retn0-srv-gcp-01 --serial --yes
```

The dedicated deploy reloads systemd only when its managed file changes. It does not start, stop, or restart Docker, Tailscale, or any container. A second apply should report zero changed operations. The guard takes effect on the next Docker activation; an approved maintenance restart or reboot is required to prove the complete boot path.

After applying, inspect the loaded configuration on the target without restarting services:

```bash
sudo systemd-analyze verify docker.service
sudo systemctl cat docker.service
sudo systemctl show docker.service \
  -p DropInPaths -p ExecStartPre -p Restart -p RestartUSec -p StartLimitIntervalUSec
```

Expect the managed drop-in, all three pre-start commands, `Restart=always`, `RestartUSec=10s`, and `StartLimitIntervalUSec=0`. After an approved restart or reboot, also check the Docker journal and the IPv4/IPv6 HTTPS health endpoints documented in the [Caddy project](../../compose/caddy-gcp/README.md#verify). To roll back the dependency, remove only `10-homelab-tailscale.conf` and reload systemd during an approved configuration change; do not disable Docker or change its other drop-ins.

### Compose stacks

Preview a stack deployment for one cloud host, then apply it only after checking that host's existing `.env`, data directory, and Beszel identity:

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --dry --diff --serial
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --serial --yes
```

The stack deploy synchronizes non-secret host values into a marked block of the target's `.env`, preserving its secret values and mode `600`. For stacks without an `.env.example` requiring host-local secrets, it can create this file from the declared non-secret values. It then uploads `compose/<stack>/compose.yaml` as `compose.pending.yaml` under `/opt/stacks/<stack>/`, validates that candidate, and only then replaces the active Compose file and calls `up`. When an `.env.example` exists, an absent `.env` stops before the active file is replaced unless explicit seeding is requested. Unlisted stacks are not stopped or deleted. Normal deployments neither upload nor replace target secrets or `data/`. Once applied, ordinary `docker compose` commands also work directly on the host.

Select one assigned stack with `--data stack=caddy-gcp` to avoid applying other projects on the selected host. The executor explicitly stages only `config/Caddyfile` alongside the GCP Caddy Compose file under `.deploy/` and runs `caddy validate` before promotion. A missing Caddyfile or a symlink at either the file or its `config/` directory stops deployment. Other stacks upload only their Compose file; environment files, private keys and runtime data are never additional deployment assets. Compose applies service or image changes without forcing unchanged containers to be recreated. The Caddy project then runs `caddy reload`; Caddy skips identical configurations without `--force`.

An explicit `--data stack_env_file=/absolute/path/to/private.env` can seed an absent target `.env` for the selected stack. The local file must have private permissions, and `--diff` is rejected for this operation. Secret values and host values are uploaded together because pyinfra plans file operations before execution. Existing remote environment files are preserved. Use this only for initial provisioning; subsequent deployments do not need the local credential file.

See [`compose/caddy-gcp/README.md`](../../compose/caddy-gcp/README.md) and [`compose/beszel-hub/README.md`](../../compose/beszel-hub/README.md) for the GCP HTTPS entrypoint, Hub deployment, and validation commands. Deploy `caddy-gcp` before `beszel-hub` so their shared Docker network exists.

The GCP and both OCI Beszel agents have been applied and verified. Each host retains its original secret-bearing Compose file as `/opt/stacks/beszel-agent/compose.pre-iac.yaml` with mode `600` for rollback; the OCI hosts also retain `.env.pre-iac`. Do not copy these files into Git. Each agent's identity remains in `/opt/stacks/beszel-agent/data/`.

`baseline.py` does not perform a whole-system package upgrade or reboot a
host. Run it twice after a change; the second run should report zero changed
operations. `maintenance.py` also never reboots hosts automatically.

## Project layout

- `inventories/production.py`: cloud inventory derived from `hosts/<hostname>/host.yaml`.
- `group_data/`: shared values and GCP/OCI-specific users.
- `deploys/`: operator-facing baseline, stack deployment, audit, verification, and maintenance entrypoints.
- `homelab_infra/`: reusable deploys and pure decision helpers.
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
