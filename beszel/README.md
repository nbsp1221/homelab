# Beszel

Lightweight server monitoring hub and agent for this repository.

Beszel provides a web dashboard showing host and per-container CPU, memory,
network, and disk statistics with historical charts and configurable alerts.
It replaces the heavier Prometheus + Grafana + Loki + Alloy stack for the
common "is everything alive and healthy?" use case.

## What This Stack Contains

- `beszel`: Hub — PocketBase-based web dashboard (port 8090)
- `beszel-agent`: Agent — collects host and Docker metrics and connects to the hub over WebSocket
- `beszel-socket-proxy`: Read-only Docker API proxy — exposes only the container endpoint on loopback

## Current Design Choices

- Hub and agent run on the same host and communicate through a shared Unix
  socket (`./beszel_socket/beszel.sock`), following the official same-system
  deployment pattern. The agent also maintains an outbound WebSocket to the
  hub via `HUB_URL`.
- The agent uses `network_mode: host` to read host network-interface stats.
  Because of this it cannot join Docker networks; container services are
  reached through host loopback.
- The hub publishes `127.0.0.1:8090` on loopback and joins `caddy-network`
  for the reverse proxy.
- The agent accesses Docker through a read-only socket proxy. The proxy exposes
  only the container API on host loopback; the agent never receives the raw
  Docker socket.
- Beszel checks for new releases and shows update notifications in the UI.

## Portability

`compose.yaml` is tracked by Git and represents this repository's NVIDIA Linux
host baseline. It contains the hub, agent, GPU, disk, S.M.A.R.T., and systemd
service monitoring, healthchecks, and Docker socket proxy.

Some values are inherently host-specific (partition names, SMART devices,
sensor exclusions, service patterns, extra filesystem paths). They live in
`compose.yaml` because this repository doubles as a shared self-hosted
configuration, but you will need to adjust them when deploying elsewhere.

## Prerequisites

- Docker Engine
- Docker Compose v2
- NVIDIA GPU and NVIDIA Container Toolkit
- External Docker network `caddy-network`
- External reverse proxy configuration that routes your Beszel domain to
  `beszel:8090` on `caddy-network`

Create the shared proxy network once if needed:

```bash
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

## Quick Start

```bash
cd beszel
cp .env.example .env
# edit .env — at minimum set BESZEL_APP_URL

# Create the marker directory used for additional filesystem monitoring.
sudo mkdir -p /mnt/data01/.beszel

# 1. Start the hub only
docker compose up -d beszel

# 2. Open http://localhost:8090, create an admin account
# 3. Go to Settings > Tokens, create a universal token
# 4. Click "Add System", copy the public key from the dialog
# 5. Paste the token and key into .env

# 6. Start the full stack
docker compose up -d

# 7. The agent registers automatically through the universal token.
#    Do not add the same system manually after starting the agent.
```

## Environment Variables

Required variables are documented in `.env.example`.

| Variable | Description |
| --- | --- |
| `BESZEL_APP_URL` | Public URL for notification links and agent config generation |
| `BESZEL_AGENT_TOKEN` | Universal token from Hub Settings > Tokens |
| `BESZEL_AGENT_KEY` | Public key from the "Add System" dialog |

To auto-create the first admin account, add `USER_EMAIL` and `USER_PASSWORD`
to the `beszel` service's `environment` block in `compose.yaml`.
If omitted, the web UI will prompt you to create an account on first visit.

## Reverse Proxy

This repository does not manage the top-level Caddy or reverse-proxy
configuration. The expected upstream pattern is:

```caddy
beszel.example.com {
    request_body {
        max_size 10MB
    }
    reverse_proxy beszel:8090 {
        transport http {
            read_timeout 360s
        }
    }
}
```

The `read_timeout 360s` is recommended by the Beszel docs for WebSocket
connections.

## Notifications

Beszel uses [Shoutrrr](https://github.com/nicholas-fedor/shoutrrr) URL
schemas. Configure in the web UI under Settings > Notifications.

Common examples:

- Telegram: `telegram://<bot-token>@telegram?chats=<chat-id>`
- Discord: `discord://<token>@<channel-id>`
- ntfy: `ntfy://:<access-token>@<host>/<topic>`

Alerts and notification channels are UI-managed and therefore intentionally
not encoded in Compose.

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

Check hub health:

```bash
docker compose exec -T beszel /beszel health --url http://localhost:8090
```

Check agent health:

```bash
docker compose exec -T beszel-agent /agent health
```
