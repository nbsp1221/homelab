# pyinfra

This executor manages the baseline configuration and explicitly selected Compose stacks on the homelab's cloud Linux hosts. pyinfra runs from `retn0-srv-main` and connects to managed hosts over Tailscale SSH. Managed hosts do not run an agent or require Python.

## Scope

- Audit existing Debian and Ubuntu hosts.
- Install the small package set required by the baseline.
- Maintain a 2 GiB disk-backed swap file.
- Install current Docker Engine and Docker Compose from Docker's official
  repository.
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

Preview a stack deployment for one cloud host, then apply it only after checking that host's existing `.env`, data directory, and Beszel identity:

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --dry --diff --serial
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --serial --yes
```

The stack deploy synchronizes non-secret host values into a marked block of the target's `.env`, preserving its secret values and mode `600`. For stacks without an `.env.example` requiring host-local secrets, it can create this file from the declared non-secret values. It then uploads `compose/<stack>/compose.yaml` as `compose.pending.yaml` under `/opt/stacks/<stack>/`, validates that candidate, and only then replaces the active Compose file and calls `up`. When an `.env.example` exists, an absent `.env` stops before the active file is replaced unless explicit seeding is requested. Unlisted stacks are not stopped or deleted. Normal deployments neither upload nor replace target secrets or `data/`. Once applied, ordinary `docker compose` commands also work directly on the host.

Select one assigned stack with `--data stack=caddy-gcp` to avoid applying other projects on the selected host. An optional `compose/<stack>/deploy.yaml` explicitly lists public `files`, a `build` boolean, and service `checks` as argument lists. Asset-backed projects are staged under `.deploy/`, built and checked before promotion, and recreated on apply to read the validated configuration. Environment files, data directories, private-key files, escaped paths, and symlinks are rejected as deployment assets. Omitted manifest fields default to no assets, build, or checks, preserving the Compose-only agent flow.

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
