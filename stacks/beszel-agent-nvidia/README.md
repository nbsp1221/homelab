# Beszel NVIDIA Agent

This stack sends Linux host, Docker, and NVIDIA GPU metrics to a [Beszel Hub](../beszel-hub/README.md). For hosts without NVIDIA GPUs, see the [standard agent](../beszel-agent/README.md).

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

Use [`.env.example`](.env.example) to set filesystem, SMART device, sensor, systemd service, and extra filesystem bind values for the target host. For an existing agent, reuse the current values to keep the same series in the Hub. The extra filesystem directory must exist on the host before deployment.

## Prerequisites

- Docker Engine
- Docker Compose v2
- NVIDIA GPU and NVIDIA Container Toolkit
- HTTPS access to the Hub and a registration for this system in the Hub

## Arcane Git Sync

Create a [Pull sync](https://getarcane.app/docs/docker/git-sync#create-a-git-synced-project) on the Agent that has the NVIDIA devices. Use `beszel-agent-nvidia` as the sync and Compose project name and `stacks/beszel-agent-nvidia/compose.yaml` as the Compose File Path. Set the variables from `.env.example` in the sync environment. Turn off the previous controller's automatic deployment for this project before saving. After deploying, check that GPU, filesystem, SMART, and Docker metrics continue to update in the Hub.

Reuse the existing Hub registration and set `BESZEL_AGENT_TOKEN_PATH` to the current token file on the host. For a new agent, register it with **Add System** and store the token in a private file with mode `0600`. The agent reads the mounted secret through `TOKEN_FILE`.

## Manual deployment

```bash
cd stacks/beszel-agent-nvidia
cp .env.example .env
# Set the host values in .env and prepare the token and extra filesystem directory.
docker compose up -d
```

## Environment Variables

Required variables are documented in `.env.example`.

| Variable | Description |
| --- | --- |
| `BESZEL_HUB_URL` | Remote Hub URL for the outbound WebSocket connection |
| `BESZEL_AGENT_KEY` | Public key from the "Add System" dialog |
| `BESZEL_AGENT_TOKEN_PATH` | Absolute path to the private token file on the target host |

For manual deployments, supply these values in a local `.env` beside the Compose file.

## Persistent state

The `beszel-agent-data` named volume stores the agent's identity. Keep the volume and its associated system registration across deployments.

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
BESZEL_AGENT_KEY=placeholder docker compose --env-file .env.example config --quiet
```

Check agent health:

```bash
docker compose exec -T beszel-agent /agent health
```
