# OpenCodex

A Docker Compose deployment of [OpenCodex](https://github.com/lidge-jun/opencodex) for remote Codex clients.

## Requirements

- Docker Engine and Docker Compose v2
- an external Docker network named `caddy-network`
- a host Codex login whose directory can be mounted read-only

Create the shared network once:

```bash
docker network inspect caddy-network >/dev/null 2>&1 || \
  docker network create caddy-network
```

## Configure

Create the local environment file:

```bash
cd compose/opencodex
cp .env.example .env
chmod 600 .env
```

Set different random values for `OPENCODEX_API_AUTH_TOKEN` and `OPENCODEX_ADMIN_AUTH_TOKEN`.
Set `CODEX_HOST_HOME` to the host directory that contains the active Codex `auth.json`.

On the first deployment, copy `config.example.json` to `config.json`, replace the example origin, and import it into the named volume:

```bash
docker compose run --rm --no-deps \
  --entrypoint sh \
  -v "$PWD/config.json:/tmp/config.json:ro" \
  opencodex -c 'test ! -e /home/node/.opencodex/config.json && cp /tmp/config.json /home/node/.opencodex/config.json'
```

The local `config.json` bootstrap copy is ignored by Git; the live configuration stays in the named volume.

If migrating from the previous bind-mounted `./data` layout, stop the old stack and copy its data into the new volume before the first start:

```bash
docker compose run --rm --no-deps \
  --entrypoint sh \
  -v "$PWD/data:/tmp/legacy-data:ro" \
  opencodex -c 'test ! -e /home/node/.opencodex/config.json && cp -a /tmp/legacy-data/. /home/node/.opencodex/'
```

This command refuses to overwrite an already initialized named volume. Keep the old `data/` directory as a rollback copy until the new deployment has been verified.

## Connect clients

Install the connector on each client machine and point it at the HTTPS URL served by your reverse proxy:

```bash
npm install --global opencodex-connect
opencodex-connect setup https://<your-domain> \
  --token YOUR_OPENCODEX_API_AUTH_TOKEN
opencodex-connect status
```

The connector writes the remote provider to the client's Codex configuration. Use `opencodex-connect restore` to return to the native Codex provider.

Open the same HTTPS URL in a browser to manage providers with `OPENCODEX_ADMIN_AUTH_TOKEN`.

## Validate and run

```bash
docker compose config -q
docker compose up -d --build
docker compose ps
```

OpenCodex is exposed only to the external `caddy-network`; it does not publish a host port.
Configure the reverse proxy to send traffic to `opencodex:10100`.

The `opencodex-data` volume stores provider configuration, credentials, usage history, and runtime state.
Back it up before upgrades or destructive Compose operations.
Do not run `docker compose down -v` unless deleting that state is intentional.

To upgrade, review the new package version in `.env`, then rebuild the image:

```bash
docker compose build --pull
docker compose up -d
```
