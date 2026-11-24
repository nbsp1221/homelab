# 🏠 Homelab

Personal homelab infrastructure and self-hosted services managed as code

This repository contains mostly independent Docker Compose stacks for self-hosted services and tools for configuring Linux hosts.

- [`compose/`](compose/): the canonical Compose definition for each adopted stack.
- [`hosts/`](hosts/): which host runs an adopted stack and its non-secret host-specific values.
- [`deploy/`](deploy/): manually invoked executors that apply those definitions.

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

One time setup:

```bash
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

## Infrastructure Automation

The [pyinfra executor](deploy/pyinfra/README.md) runs from a controller with SSH access to the managed hosts. It manages the GCP and OCI Linux baseline and can apply selected stacks assigned in [`hosts/`](hosts/). Run pyinfra explicitly when applying infrastructure changes.

## Testing

- **Compose**. Run `pnpm install --frozen-lockfile` and `pnpm lint` from the repository root.
- **pyinfra**. Follow the [pyinfra setup and validation commands](deploy/pyinfra/README.md#validation). The test suite uses synthetic fixtures and runs locally. The separate inventory check validates the repository's deployment configuration.
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
| Monitoring | [`monitoring/`](monitoring/) | Prometheus + node-exporter + cAdvisor + Grafana. See `monitoring/README.md`. |
| Infisical | [`infisical/`](infisical/) | Secrets management platform with Postgres and Redis. See `infisical/README.md`. |
| Karakeep | [`karakeep/`](karakeep/) | Bookmark manager with full-text search and optional AI tagging/summaries. See `karakeep/README.md`. |
| LiteLLM Proxy + Postgres | [`litellm/`](litellm/) | Standardized LLM proxy. See `litellm/README.md`. |
| Bifrost AI Gateway | [`compose/bifrost/`](compose/bifrost/) | OpenAI-compatible AI gateway. |
| n8n | [`compose/n8n/`](compose/n8n/) | Workflow automation stack with Postgres and internal Redis for workflow shared state. See `compose/n8n/README.md`. |
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
