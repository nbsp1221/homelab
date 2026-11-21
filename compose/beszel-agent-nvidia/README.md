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

Review the filesystem, SMART devices, sensor exclusions, systemd service patterns, and extra filesystem bind mounts in [`compose.yaml`](compose.yaml) for the target host. For example, set the extra filesystem bind source to a directory on the filesystem you want to monitor, such as `/path/to/extra-filesystem/.beszel`, and create that directory before starting the stack.

## Prerequisites

- Docker Engine
- Docker Compose v2
- NVIDIA GPU and NVIDIA Container Toolkit
- HTTPS access to the Hub and a registration for this system in the Hub

## Komodo

Select the target server and the Repo containing this definition. For a server named `host-01`, use the Stack name `beszel-agent-host-01` and the run directory `compose/beszel-agent-nvidia`. Set Project Name to `beszel-agent-nvidia` to match the Compose project and supply `BESZEL_HUB_URL` and `BESZEL_AGENT_KEY` in the Stack environment. After deploying, check that GPU, filesystem, and Docker metrics are updating in the Hub.

Register the host with **Add System** in Beszel. On the target host, store its token as one line in the file identified by `secrets.beszel_agent_token.file` in [`compose.yaml`](compose.yaml). Use mode `600` and keep the file outside Git. The agent reads the mounted secret through `TOKEN_FILE` in both Komodo and manual deployments.

## Manual deployment

```bash
cd compose/beszel-agent-nvidia
cp .env.example .env
# Set BESZEL_HUB_URL and BESZEL_AGENT_KEY in .env, then prepare the token and extra filesystem directory described above.
docker compose up -d
```

## Environment Variables

Required variables are documented in `.env.example`.

| Variable | Description |
| --- | --- |
| `BESZEL_HUB_URL` | Remote Hub URL for the outbound WebSocket connection |
| `BESZEL_AGENT_KEY` | Public key from the "Add System" dialog |

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
BESZEL_HUB_URL=https://beszel.example.com BESZEL_AGENT_KEY=placeholder docker compose config -q
```

Check agent health:

```bash
docker compose exec -T beszel-agent /agent health
```
