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

Cloud resources, Tailscale enrollment, firewalls, and secrets are outside this executor. The OS baseline does not automatically deploy application stacks.

## Controller setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on
`retn0-srv-main`, then synchronize the locked Python 3.12 environment:

```bash
cd /home/retn0/deploy/homelab/deploy/pyinfra
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

Preview the stack deployment plan for the GCP pilot, then apply it only after checking the target's existing `.env`, data directory, and Beszel identity:

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --dry --diff --serial
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --serial --yes
```

The stack deploy uploads `compose/<stack>/compose.yaml` to `/opt/stacks/<stack>/`, validates it, and calls Compose `up` without deleting or stopping unlisted stacks. Host-specific non-secret values come from `hosts/`; the target's `.env` and `data/` are neither uploaded nor replaced. The pilot only needs its Compose file; additional tracked configuration or build assets must be explicitly supported before another stack is adopted.

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
