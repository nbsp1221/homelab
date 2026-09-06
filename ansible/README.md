# Ansible

This directory manages the baseline configuration of the homelab's Linux
hosts. Ansible runs from `retn0-srv-main` and connects to managed hosts over
Tailscale SSH.

## Scope

- Bootstrap and audit existing Debian and Ubuntu hosts.
- Install the small package set required by the baseline.
- Maintain a 2 GiB disk-backed swap file.
- Install Docker Engine and Docker Compose from Docker's official repository.
- Run operating-system package upgrades only when explicitly requested.

Cloud resources, Tailscale enrollment, firewalls, application stacks, and
secrets are outside the initial baseline.

## Controller setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on
`retn0-srv-main`, then synchronize the locked Python 3.12 environment:

```bash
cd /home/retn0/deploy/homelab/ansible
uv sync --locked
```

uv selects Python from `.python-version`, creates `.venv`, and installs the
exact dependency graph recorded in `uv.lock`. The `.venv` directory is local
runtime state and must not be committed.

## Validation

Run commands from this directory:

```bash
uv run ansible-inventory --graph
uv run ansible-playbook playbooks/bootstrap.yml --syntax-check
uv run ansible-playbook playbooks/audit.yml --syntax-check
uv run ansible-playbook playbooks/site.yml --syntax-check
uv run ansible-playbook playbooks/maintenance.yml --syntax-check
uv run ansible-lint .
```

## Operation

Bootstrap a new Debian or Ubuntu host before its first audit or preview:

```bash
uv run ansible-playbook playbooks/bootstrap.yml \
  --limit retn0-srv-gcp-01
```

The bootstrap play installs only the Python bindings required by the baseline
and is safe to run again.

Audit without making changes:

```bash
uv run ansible-playbook playbooks/audit.yml
```

Preview the baseline against one host:

```bash
uv run ansible-playbook playbooks/site.yml \
  --check --diff --limit retn0-srv-gcp-01
```

Apply the baseline to one host:

```bash
uv run ansible-playbook playbooks/site.yml \
  --limit retn0-srv-gcp-01
```

Apply explicit package maintenance:

```bash
uv run ansible-playbook playbooks/maintenance.yml \
  --limit retn0-srv-gcp-01
```

`site.yml` does not perform a system-wide package upgrade or reboot a host.
Run it twice after a change; the second run should report `changed=0`.

## Updating controller dependencies

Change version constraints in `pyproject.toml`, then deliberately refresh and
verify the lockfile:

```bash
uv lock --upgrade
uv sync --locked
uv run ansible-lint .
```

Commit `pyproject.toml` and `uv.lock` together.
