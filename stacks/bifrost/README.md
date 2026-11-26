# Bifrost

Bifrost AI Gateway running behind the repository's external Caddy network.

This stack:

- builds the version-pinned `maximhq/bifrost` v2.0.0 source tag with the local alias-body patch overlay
- joins the external Docker network `caddy-network`
- does not publish ports to the host
- expects your reverse proxy to route to `bifrost:8080`
- persists Bifrost SQLite state in the `bifrost-data` Docker volume

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
cd stacks/bifrost
cp .env.example .env
chmod 600 .env
printf 'BIFROST_ENCRYPTION_KEY=%s\n' "$(openssl rand -hex 32)" > .env
printf 'BIFROST_SETUP_TOKEN=%s\n' "$(openssl rand -hex 32)" >> .env

docker compose up -d --build
docker compose ps
docker compose logs -f
```

## Arcane Git Sync

Create a [Pull sync](https://getarcane.app/docs/docker/git-sync#create-a-git-synced-project) with the project name `bifrost` and Compose File Path `stacks/bifrost/compose.yaml`. Enable **Sync Files** for the Dockerfile, patch, and build context. For an existing gateway, preserve the current `BIFROST_ENCRYPTION_KEY` and volume. Use the existing key in the private sync environment and verify a request through a configured provider after the cutover.

## Secrets

- `BIFROST_ENCRYPTION_KEY` encrypts stored provider keys and other secrets. Back it up with the volume. Changing the key can make existing secrets unreadable.
- `BIFROST_SETUP_TOKEN` authorizes creation of the first admin account on a fresh deployment. It is not needed for normal operation after an admin exists.

## Configuration

This stack intentionally runs Bifrost in Web UI configuration mode.
When no config file is present, Bifrost stores configuration in SQLite under `/app/data` in the container.

The Compose file provides non-secret runtime settings directly:

- `APP_HOST=0.0.0.0`
- `APP_PORT=8080`
- `APP_DIR=/app/data`
- `LOG_LEVEL=info`
- `LOG_STYLE=json`
- `GOGC=200`
- `GOMEMLIMIT=900MiB`

Dashboard authentication, providers, provider keys, virtual keys, and other gateway settings should be configured through the Bifrost dashboard.

## Reverse Proxy

Example Caddyfile snippet:

```caddy
bifrost.example.com {
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

The `bifrost-data` volume is mounted at `/app/data` in the container. With the default Compose project name, Docker calls the volume `bifrost_bifrost-data`.

For an existing installation that bind-mounts `./data/`, stop Bifrost and copy the entire directory into the volume, preserving ownership and permissions. Use the same encryption key when starting Bifrost with the volume.

Back up:

- the `bifrost-data` volume
- `BIFROST_ENCRYPTION_KEY`

## References

- Project: https://github.com/maximhq/bifrost
- Gateway setup: https://docs.getbifrost.ai/quickstart/gateway/setting-up
- Config file guide: https://docs.getbifrost.ai/deployment-guides/config-json
- Docker tuning: https://docs.getbifrost.ai/deployment-guides/docker-tuning
