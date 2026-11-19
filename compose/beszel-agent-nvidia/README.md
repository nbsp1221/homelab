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

Create a Stack named `beszel-agent-nvidia` on `retn0-srv-main` with the `homelab` Repo and `compose/beszel-agent-nvidia` as the run directory. Use the default Project Name so Komodo and Docker Compose use the same project name. Set the existing system's `BESZEL_HUB_URL` and `BESZEL_AGENT_KEY` in the Stack environment. After deploying, check that GPU, filesystem, and Docker metrics are updating in the Hub.

Store the existing system token as a single line in `/etc/komodo/secrets/beszel-agent-nvidia.token` with mode `600`. Compose mounts this file for the agent, which reads it through `TOKEN_FILE`. The host file stays outside Git and is shared by Komodo and manual Compose deployment.

## Manual deployment

```bash
cd compose/beszel-agent-nvidia
cp .env.example .env
# Register this host using Add System in the target Hub.
# Set BESZEL_HUB_URL and BESZEL_AGENT_KEY in .env.
# Put the system token in the host file described above.

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
| `BESZEL_AGENT_KEY` | Public key from the "Add System" dialog |

For manual deployments, supply these values in a local `.env` beside the Compose file.

## Persistent state

The `beszel-agent-nvidia` project stores the agent's persistent identity in `beszel-agent-nvidia_beszel-agent-data`. When migrating from the `beszel` project, copy the existing state from `beszel_beszel-agent-data` before starting the new project. The old and new projects use the same container names, so take the old project down with its volume intact before deploying the new one.

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
