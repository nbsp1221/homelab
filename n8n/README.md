# n8n

n8n stack for this repository.

This directory is the canonical n8n deployment definition for this repository.
It runs n8n in regular mode behind an external reverse proxy and keeps supporting services private on an internal Docker network.

## What This Stack Contains

- `n8n`: UI, API, and public webhooks
- `postgres`: main n8n database
- `redis`: internal shared-state store for workflows

Important: Redis is not used for n8n queue mode here.
It exists only for workflow-level shared state such as TTL-based keys accessed through the built-in Redis node or Redis Trigger.

## Current Design Choices

- n8n runs in regular mode, not queue mode
- public UI and public webhooks use the same external domain
- TLS terminates at the external reverse proxy
- Redis is internal-only, password-protected, and persisted with a named Docker volume
- `NODE_FUNCTION_ALLOW_BUILTIN=*` remains enabled for compatibility with existing Code-node-heavy workflows

That last point is a compatibility choice, not a hardening best practice.

## Prerequisites

- Docker Engine
- Docker Compose v2
- External Docker network `caddy-network`
- External reverse proxy configuration that routes your n8n domain to `n8n:5678` on `caddy-network`

Create the shared proxy network once if needed:

```bash
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

## Quick Start

```bash
cd n8n
cp .env.example .env
# edit .env before first start

docker compose up -d
docker compose ps
docker compose logs -f
```

## Environment Variables

Required variables are documented in `.env.example`.
The most important ones are:

- Postgres credentials and database names
- `N8N_HOST`
- `WEBHOOK_URL`
- `N8N_PROXY_HOPS`
- `N8N_ENCRYPTION_KEY`
- `REDIS_PASSWORD`

`WEBHOOK_URL` must match the real external URL used by the reverse proxy.
Because n8n runs behind a proxy, `N8N_PROXY_HOPS=1` is part of the expected baseline.

## Reverse Proxy

This repository does not manage the top-level Caddy or reverse-proxy configuration.
The expected upstream pattern is:

```caddy
n8n.example.com {
    reverse_proxy n8n:5678
}
```

The `n8n` service joins `caddy-network`, but `postgres` and `redis` do not.

## Redis Usage

Redis in this stack is meant for workflow shared state only.

- no host port is published
- access is limited to `n8n-network`
- a password is required
- data persists across normal `docker compose down` / `up` cycles

When creating an n8n Redis credential, use:

- Host: `redis`
- Port: `6379`
- Password: value of `REDIS_PASSWORD`
- Database Number: usually `0`

## Compatibility Note

`NODE_FUNCTION_ALLOW_BUILTIN=*` is intentionally left enabled in the Compose file.
This keeps existing Code node patterns working during the move into this repository.
If the workflow estate becomes more controlled later, that setting should be revisited separately.

## Migration Note

Migration from the old standalone n8n repository is a separate manual process.
This stack definition only describes the canonical target deployment in this repository.

## Operations

```bash
docker compose pull
docker compose up -d
docker compose logs -f
docker compose restart
docker compose down
```

## Verification

Validate the stack file:

```bash
docker compose config -q
```

Check application health:

```bash
docker compose exec -T n8n wget -qO- http://127.0.0.1:5678/healthz
```

Check database readiness:

```bash
docker compose exec -T postgres pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}"
```
