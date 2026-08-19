# Bifrost

Bifrost AI Gateway running behind the repository's external Caddy network.

This stack:

- builds the version-pinned `maximhq/bifrost` v1.6.11 source tag with the local alias-body patch overlay
- joins the external Docker network `caddy-network`
- does not publish ports to the host
- expects your reverse proxy to route to `bifrost:8080`
- persists Bifrost SQLite state under `./data/`

## Prerequisites

- Docker Engine
- Docker Compose v2
- External Docker network `caddy-network`
- External reverse proxy configuration that routes your Bifrost domain to `bifrost:8080`

Create the shared proxy network once if needed:

```bash
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

## Quick Start

```bash
cd compose/bifrost
cp .env.example .env
chmod 600 .env
printf 'BIFROST_ENCRYPTION_KEY=%s\n' "$(openssl rand -hex 32)" > .env

docker compose up -d --build
docker compose ps
docker compose logs -f
```

## Encryption Key

```bash
# BIFROST_ENCRYPTION_KEY
openssl rand -hex 32
```

Keep `BIFROST_ENCRYPTION_KEY` backed up with `./data/`.
Once the database is populated, changing the encryption key can make stored secrets unreadable.

## Configuration

This stack intentionally runs Bifrost in Web UI configuration mode.
Do not commit `data/config.json`; when no config file is present, Bifrost stores configuration in SQLite under `./data/`.

The Compose file provides non-secret runtime settings directly:

- `APP_HOST=0.0.0.0`
- `APP_PORT=8080`
- `APP_DIR=/app/data`
- `LOG_LEVEL=info`
- `LOG_STYLE=json`
- `GOGC=200`
- `GOMEMLIMIT=900MiB`

The only value expected in `.env` is `BIFROST_ENCRYPTION_KEY`, which is used to encrypt stored provider keys and other secrets in the SQLite config database.

Dashboard authentication, providers, provider keys, virtual keys, and other gateway settings should be configured through the Bifrost dashboard.

## Reverse Proxy

Example Caddyfile snippet:

```caddy
bifrost.retn0.kr {
  reverse_proxy bifrost:8080
}
```

## Verification

Validate the stack file:

```bash
docker compose config -q
```

Check health from inside the container:

```bash
docker compose exec -T bifrost wget -qO- http://127.0.0.1:8080/health
```

## Operations

```bash
docker compose build --pull
docker compose up -d
docker compose logs -f
docker compose restart
docker compose down
```

## Data Persistence / Backups

Persistent runtime data is stored in `./data/`.

Back up:

- `./data/`
- `BIFROST_ENCRYPTION_KEY`

## References

- Project: https://github.com/maximhq/bifrost
- Gateway setup: https://docs.getbifrost.ai/quickstart/gateway/setting-up
- Config file guide: https://docs.getbifrost.ai/deployment-guides/config-json
- Docker tuning: https://docs.getbifrost.ai/deployment-guides/docker-tuning
