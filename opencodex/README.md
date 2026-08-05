# OpenCodex

A minimal Docker deployment of the upstream
[OpenCodex](https://github.com/lidge-jun/opencodex) proxy for remote Codex clients.

This stack only packages and runs the official npm release. It does not patch
OpenCodex, synchronize client model catalogs, or manage client configuration.
Clients connect with
[opencodex-connect](https://github.com/nbsp1221/opencodex-connect).

## What is included

- One OpenCodex container built from `@bitkyc08/opencodex`
- One local data directory for providers, credentials, and dashboard settings
- Admission-token authentication for `/v1/*`
- Separate admin-token authentication for `/api/*`
- Host Codex OAuth as the default OpenAI pool account
- Caddy-only network access; no host port is published

The initial [`config.example.json`](config.example.json) binds OpenCodex to
`0.0.0.0:10100` and allows the production dashboard origin. Its OpenAI provider
starts in `pool` mode, which is the upstream default. The host's Codex home is
mounted read-only, and its `auth.json` is exposed to OpenCodex as the pool's main
account.

OpenCodex stores its live configuration and runtime state under `./data/`. This
directory is bind-mounted at `/home/node/.opencodex` and ignored by Git because
`data/config.json` can contain provider API keys. Only the non-secret example is
committed.

## Start

```sh
cd opencodex
cp .env.example .env
cp config.example.json data/config.json
chmod 700 data
chmod 600 data/config.json
```

Generate two different secrets and place them in `.env`:

```sh
openssl rand -hex 32
openssl rand -hex 32
```

Set `CODEX_HOST_HOME` to the host directory containing the active Codex
`auth.json`. The default host installation uses `~/.codex`.

Then validate and start the stack:

```sh
docker compose config
docker compose up --detach --build
docker compose ps
docker compose logs --follow opencodex
```

The proxy is reachable only through Caddy at `https://opencodex.retn0.kr`.

## Connect Codex

Install the connector on each client machine:

```sh
npm install --global opencodex-connect
opencodex-connect setup https://opencodex.retn0.kr \
  --token YOUR_OPENCODEX_API_AUTH_TOKEN
opencodex-connect status
```

The connector writes the remote provider directly to the client's `config.toml`
and migrates resumable session metadata. Codex fetches its model picker from
OpenCodex `/v1/models`; this server does not ship a catalog sidecar.

To return a client to native Codex routing:

```sh
opencodex-connect restore
```

## Configure providers

Open `https://opencodex.retn0.kr`, enter `OPENCODEX_ADMIN_AUTH_TOKEN`, and add
providers from the dashboard. Provider configuration persists in the
Git-ignored `./data/config.json` file.

The dashboard does not currently expose every provider field. For settings such
as custom headers, stop OpenCodex, edit `data/config.json` directly, and start it
again:

```sh
docker compose stop
${EDITOR:-vi} data/config.json
docker compose up --detach
```

Never commit `data/config.json`; provider credentials and upstream gateway keys
may be stored in it.

The upstream-default OpenAI pool starts with the host's Codex OAuth as its main
account. Additional Codex accounts can be added from the dashboard.

The host Codex directory is read-only inside the container. OpenCodex reads its
OAuth token but cannot modify the host's Codex configuration or credentials.
Host Codex remains responsible for refreshing `auth.json`; because the directory
is mounted rather than the individual file, atomic token replacements become
visible to OpenCodex without rebuilding the container.

The data-plane and admin tokens serve different purposes and must not be equal.
Do not commit `.env`.

## Upgrade

Update `OPENCODEX_VERSION` in `.env` and `.env.example`, then rebuild:

```sh
docker compose build --pull
docker compose up --detach
```

Provider configuration remains under `./data/`.

## Stop or reset

Remove the container while preserving OpenCodex configuration:

```sh
docker compose down
```

To reset OpenCodex, stop the stack and remove the contents of `./data/`, then
copy `config.example.json` back to `data/config.json`. Back up `./data/` before
doing so; it contains credentials, settings, usage data, and runtime state.
