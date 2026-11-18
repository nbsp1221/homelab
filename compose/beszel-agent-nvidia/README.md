# Beszel NVIDIA Agent

The NVIDIA agent on `retn0-srv-main` reports to the [GCP Hub](../beszel-hub/README.md) at `https://beszel.retn0.dev`. The GCP and OCI hosts use the [cloud agent definition](../beszel-agent/README.md). Each system has its own token.

Beszel provides a web dashboard showing host and per-container CPU, memory, network, and disk statistics with historical charts and configurable alerts.
It replaces the heavier Prometheus + Grafana + Loki + Alloy stack for the common "is everything alive and healthy?" use case.

## What This Stack Contains

- `beszel-agent`: Agent — collects host and Docker metrics and connects to the hub over WebSocket
- `beszel-socket-proxy`: Read-only Docker API proxy — exposes only the container endpoint on loopback

## Current Design Choices

- The agent connects to the remote Hub through an outbound HTTPS WebSocket using `BESZEL_HUB_URL` and a system-specific token. `DISABLE_SSH=true` disables its inbound listener.
- The agent uses `network_mode: host` to read host network-interface stats.
  Because of this it cannot join Docker networks; container services are reached through host loopback.
- The agent accesses Docker through a read-only socket proxy.
  The proxy exposes only the container API on host loopback; the agent never receives the raw Docker socket.

## Portability

`compose.yaml` is tracked by Git and represents this repository's NVIDIA Linux host baseline.
It contains the agent, GPU, disk, S.M.A.R.T., and systemd service monitoring, healthchecks, and Docker socket proxy.

Some values are inherently host-specific (partition names, SMART devices, sensor exclusions, service patterns, extra filesystem paths).
They live in `compose.yaml` because this repository doubles as a shared self-hosted configuration, but you will need to adjust them when deploying elsewhere.

## Prerequisites

- Docker Engine
- Docker Compose v2
- NVIDIA GPU and NVIDIA Container Toolkit
- Access to the remote Hub over Tailscale and a registration for this system in that Hub

## Komodo

Select `retn0-srv-main` and the homelab Git repository. Set the run directory to `compose/beszel-agent-nvidia` and the Compose project name to `beszel`, matching the existing deployment. Reuse this host's Hub URL, public key, and token in the Stack environment. After deploying, check that GPU, filesystem, and Docker metrics are updating in the Hub.

## Manual deployment

```bash
cd compose/beszel-agent-nvidia
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
| `BESZEL_HUB_URL` | Remote Hub URL for the outbound WebSocket connection |
| `BESZEL_AGENT_TOKEN` | This system's individual token from Add System |
| `BESZEL_AGENT_KEY` | Public key from the "Add System" dialog |

Keep the token and any registration scripts outside Git. For manual deployments, supply the values in a private `.env` beside the Compose file.

## Persistent state

The `beszel` Compose project resolves `beszel-agent-data` to the existing `beszel_beszel-agent-data` volume, which stores the agent's persistent identity. Keep this volume across deployments.

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

Check agent health:

```bash
docker compose exec -T beszel-agent /agent health
```
