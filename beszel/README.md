# Beszel

The main-host NVIDIA agent reports to the GCP Hub at `https://beszel.retn0.dev`, together with the GCP and both OCI agents. Each system has its own token. The old main-host Hub is stopped, and its definition and data are retained for rollback under the optional `legacy` profile; its URL is `https://beszel-legacy.retn0.dev` when restarted. The separate desktop will be registered later.

Beszel provides a web dashboard showing host and per-container CPU, memory, network, and disk statistics with historical charts and configurable alerts.
It replaces the heavier Prometheus + Grafana + Loki + Alloy stack for the common "is everything alive and healthy?" use case.

## What This Stack Contains

- `beszel`: Optional legacy Hub — PocketBase-based web dashboard (port 8090)
- `beszel-agent`: Agent — collects host and Docker metrics and connects to the hub over WebSocket
- `beszel-socket-proxy`: Read-only Docker API proxy — exposes only the container endpoint on loopback

## Current Design Choices

- The agent connects to the remote Hub through an outbound HTTPS WebSocket using `BESZEL_HUB_URL` and a system-specific token. `DISABLE_SSH=true` disables its inbound listener, and it no longer mounts the legacy Hub's Unix socket.
- The agent uses `network_mode: host` to read host network-interface stats.
  Because of this it cannot join Docker networks; container services are reached through host loopback.
- The optional legacy Hub publishes `127.0.0.1:8090` on loopback and joins `caddy-network` for the reverse proxy. Normal `docker compose up -d` starts the agent and socket proxy without starting the legacy Hub.
- The agent accesses Docker through a read-only socket proxy.
  The proxy exposes only the container API on host loopback; the agent never receives the raw Docker socket.
- Beszel checks for new releases and shows update notifications in the UI.

## Portability

`compose.yaml` is tracked by Git and represents this repository's NVIDIA Linux host baseline.
It contains the hub, agent, GPU, disk, S.M.A.R.T., and systemd service monitoring, healthchecks, and Docker socket proxy.

Some values are inherently host-specific (partition names, SMART devices, sensor exclusions, service patterns, extra filesystem paths).
They live in `compose.yaml` because this repository doubles as a shared self-hosted configuration, but you will need to adjust them when deploying elsewhere.

## Prerequisites

- Docker Engine
- Docker Compose v2
- NVIDIA GPU and NVIDIA Container Toolkit
- External Docker network `caddy-network`
- Access to the remote Hub over Tailscale and a registration for this system in that Hub
- For the optional legacy Hub, a reverse proxy route to `beszel:8090` on `caddy-network`

Create the shared proxy network once if needed:

```bash
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

## Quick Start

```bash
cd beszel
cp .env.example .env
# Register this host using Add System in the target Hub.
# Set BESZEL_HUB_URL and copy that Hub's public key and this system's token.
# Keep the populated .env private and outside Git history.

# Create the marker directory used for additional filesystem monitoring.
sudo mkdir -p /mnt/data01/.beszel

# Start the NVIDIA agent and its Docker socket proxy.
docker compose up -d
```

## Environment Variables

Required variables are documented in `.env.example`.

| Variable | Description |
| --- | --- |
| `BESZEL_APP_URL` | Optional legacy Hub URL for notification links |
| `BESZEL_HUB_URL` | Remote Hub URL for the outbound WebSocket connection |
| `BESZEL_AGENT_TOKEN` | This system's individual token from Add System |
| `BESZEL_AGENT_KEY` | Public key from the "Add System" dialog |

Keep Hub login credentials and any one-time registration or deployment scripts outside the repository. Apply credentials from a private file and recreate only the agent through pyinfra; preserve its existing data volume and the socket proxy.

## Legacy Hub and rollback

The `legacy` profile follows [Docker Compose's standard optional-service mechanism](https://docs.docker.com/compose/how-tos/profiles/). It retains the Hub definition and database volume without starting the Hub during normal agent deployments.

```bash
docker compose --profile legacy up -d beszel
docker compose --profile legacy stop beszel
```

Restarting the legacy Hub does not redirect the agent. To revert the migration, restore the previous Compose file and private `.env` from an operator-held backup, then recreate the agent while preserving `beszel-agent-data`. Never run `docker compose down --volumes`; the Hub database and agent identity must survive rollback. Leave the separate desktop's later setup outside this migration.

## Reverse Proxy

This repository does not manage the top-level Caddy or reverse-proxy configuration.
The expected upstream pattern is:

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

The `read_timeout 360s` is recommended by the Beszel docs for WebSocket connections.

## Notifications

Beszel uses [Shoutrrr](https://github.com/nicholas-fedor/shoutrrr) URL schemas.
Configure in the web UI under Settings > Notifications.

Common examples:

- Telegram: `telegram://<bot-token>@telegram?chats=<chat-id>`
- Discord: `discord://<token>@<channel-id>`
- ntfy: `ntfy://:<access-token>@<host>/<topic>`

Alerts and notification channels are UI-managed and therefore intentionally not encoded in Compose.

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

Check the optional legacy Hub's health when it is running:

```bash
docker compose --profile legacy exec -T beszel /beszel health --url http://localhost:8090
```

Check agent health:

```bash
docker compose exec -T beszel-agent /agent health
```
