# 🏠 Homelab

Personal homelab infrastructure and self-hosted services managed as code

This repository contains mostly independent Docker Compose stacks for self-hosted services and tools for configuring Linux hosts.

- [`stacks/`](stacks/) holds new stack definitions. Each stack starts with `README.md`, `.env.example`, and `compose.yaml`.
- [`compose/`](compose/) holds existing stack definitions during the transition.
- [`pyinfra/`](pyinfra/): host inventory, Docker installation, and infrastructure operations.
- [`arcane/syncs/`](arcane/syncs/): per-environment Arcane Git Pull configuration.

## Table of Contents

- [🏠 Homelab](#-homelab)
  - [Table of Contents](#table-of-contents)
  - [Prerequisites](#prerequisites)
  - [Infrastructure Automation](#infrastructure-automation)
  - [Testing](#testing)
  - [Quick Start](#quick-start)
  - [Services](#services)
    - [Maintained Services](#maintained-services)
    - [Legacy Services](#legacy-services)
  - [Reverse Proxy](#reverse-proxy)
  - [Data and Secrets](#data-and-secrets)
  - [License](#license)

## Prerequisites

- Docker Engine
- Docker Compose v2 (use `docker compose`, not `docker-compose`)
- Optional: a reverse proxy (Caddy, Traefik, nginx, etc.)

Most maintained stacks attach to an external Docker network named `caddy-network`
so a reverse proxy can route traffic to them without exposing ports on the host.

If you use this repository's [Caddy stack](compose/caddy-gcp/README.md#install-and-recover), start it first. Its Compose project creates and owns the network.

On other hosts, create the network once before starting a stack that requires it. This also applies if you run without a reverse proxy.

```bash
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

## Infrastructure Automation

Run [pyinfra](pyinfra/README.md) from a controller with SSH access to configure the GCP and OCI Linux baseline or install Docker on the mini server. Use the Compose procedures for [Caddy](compose/caddy-gcp/README.md), [Arcane Manager](stacks/arcane/README.md), and [Arcane Agent](stacks/arcane-agent/README.md). Use [Arcane Git Pull](arcane/syncs/README.md) for routine application updates.

## Testing

- **Compose**. Run `pnpm install --frozen-lockfile` and `pnpm lint` from the repository root to check `compose/` and `stacks/`.
- **pyinfra**. Follow the [pyinfra setup and validation commands](pyinfra/README.md#validation). The test suite uses synthetic fixtures and runs locally. The separate inventory check validates the repository's deployment configuration.
- **RisuAI**. Check out the upstream revision pinned in the [Dockerfile](risuai/Dockerfile) and apply the repository's [patch series](risuai/patches/series) with [`apply-patches.sh`](risuai/patches/apply-patches.sh). Run the regression test against the patched checkout. It was verified with Node.js 24.

```bash
homelab_repo="$PWD"
risuai_source=/path/to/risuai-checkout
(cd "$risuai_source" && PATCH_DIR="$homelab_repo/risuai/patches" sh "$homelab_repo/risuai/patches/apply-patches.sh")
RISUAI_SOURCE_DIR="$risuai_source" node --test --test-timeout=3000 risuai/tests/mobile-background-stream.test.mjs
```

## Quick Start

1. Pick a service directory (example: `litellm/`).
2. If the directory has `.env.example`, copy it to `.env` and edit it.
   - Some stacks (for example `openclaw/`) use a setup script instead; follow the service README.
3. Start the stack:

```bash
cd litellm
cp .env.example .env
docker compose up -d
docker compose logs -f
```

Common commands (run inside a service directory):

```bash
docker compose ps
docker compose logs -f
docker compose pull
docker compose up -d
docker compose down
```

## Services

### Maintained Services

| Service | Path | Notes |
| --- | --- | --- |
| Arcane | [`stacks/arcane/`](stacks/arcane/) | Docker management and monitoring. See [setup and verification](stacks/arcane/README.md). |
| Arcane Agent | [`stacks/arcane-agent/`](stacks/arcane-agent/) | Connects a remote Docker host to Arcane Manager. |
| Monitoring | [`monitoring/`](monitoring/) | Prometheus + node-exporter + cAdvisor + Grafana. See `monitoring/README.md`. |
| Infisical | [`infisical/`](infisical/) | Secrets management platform with Postgres and Redis. See `infisical/README.md`. |
| Karakeep | [`karakeep/`](karakeep/) | Bookmark manager with full-text search and optional AI tagging/summaries. See `karakeep/README.md`. |
| LiteLLM Proxy + Postgres | [`litellm/`](litellm/) | Standardized LLM proxy. See `litellm/README.md`. |
| Beszel Hub | [`stacks/beszel-hub/`](stacks/beszel-hub/) | Host and Docker monitoring. |
| Beszel Agent | [`stacks/beszel-agent/`](stacks/beszel-agent/) | Host and Docker metrics. See also the [NVIDIA variant](stacks/beszel-agent-nvidia/). |
| Bifrost AI Gateway | [`stacks/bifrost/`](stacks/bifrost/) | OpenAI-compatible AI gateway. |
| PocketRisu | [`stacks/pocketrisu/`](stacks/pocketrisu/) | Self-hosted AI chat application. |
| n8n | [`n8n/`](n8n/) | Workflow automation stack with Postgres and internal Redis for workflow shared state. See `n8n/README.md`. |
| OpenClaw Gateway + CLI | [`openclaw/`](openclaw/) | Agent gateway and CLI onboarding. See `openclaw/README.md` (then run `cd openclaw && python3 setup.py`). |
| OpenCodex | [`compose/opencodex/`](compose/opencodex/) | Minimal remote OpenCodex proxy for Codex CLI, App, and IDE clients. See `compose/opencodex/README.md`. |
| RisuAI | [`risuai/`](risuai/) | Web app, expects a reverse proxy on `caddy-network`. Persistent data in `risuai/save/`. |

### Legacy Services

| Service | Path | Notes |
| --- | --- | --- |
| code-server | [`code-server/`](code-server/) | Kept for reference. May be outdated or broken. |
| development-all | [`development-all/`](development-all/) | Kept for reference. May be outdated or broken. |
| development-python3 | [`development-python3/`](development-python3/) | Kept for reference. May be outdated or broken. |

- `code-server/`, `development-all/`, and `development-python3/` are not actively maintained.
- They are preserved for historical context and prior experiments (see git history).

## Reverse Proxy

This repo does not ship a top-level reverse proxy configuration.
The intended pattern is:

- Run your reverse proxy separately (often on the same host).
- Attach it to `caddy-network`.
- Configure it to route to service DNS names on that network (for example `litellm:4000`).

Each maintained service directory documents its expected upstream configuration.

## Data and Secrets

- Treat `.env` files as secrets. They are gitignored and should not be committed.
- Persistent state is stored in Docker volumes and/or host directories inside each service folder (for example `risuai/save/`).
- Back up stateful directories/volumes before upgrades.

## License

See `LICENSE`.
