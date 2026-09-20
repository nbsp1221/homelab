# Beszel cloud agent

This standalone Compose project runs an outbound-only Beszel agent on a cloud host. The Hub and NVIDIA-specific main-host agent remain in [`beszel/`](../../beszel/README.md). The first managed target is `retn0-srv-gcp-01`; do not deploy a second agent on that host.

The agent uses host networking for host interface metrics, but `DISABLE_SSH=true` disables its inbound SSH listener. It sends a WebSocket connection to the Hub through Tailscale Serve.

Docker container monitoring is deliberately disabled with `DOCKER_HOST=""`. The GCP host currently runs only this agent, so Docker access adds privilege without useful workload metrics. If a future host has Docker workloads to monitor, decide its socket policy then; the main host already uses a restricted socket proxy.

## Host prerequisites

- Docker Engine and Compose, already installed by the `pyinfra` baseline.
- Tailscale connectivity to the main host.
- On the main host, `tailscale serve --bg 8090` forwards the existing loopback-only Hub to `https://retn0-srv-main.tail8642da.ts.net` within the tailnet. Check `tailscale serve status` before changing an existing Serve configuration; never use Funnel for this service.
- A Beszel Hub public key and universal token. Keep both in the host-local `.env`, not in Git.

## First deployment

Place this directory at `/opt/stacks/beszel-agent` on the target host. Copy `.env.example` to `.env`, set the real key and token, and restrict the file to the operator account. Keep `./data` persistent: Beszel stores the agent identity there.

```bash
cd /opt/stacks/beszel-agent
chmod 600 .env
docker compose config --quiet
docker compose up -d
docker compose ps
docker compose exec -T beszel-agent /agent health
```

The Hub should show one online entry for the host. Do not create another Hub system record when a universal token has already registered this agent.

For an existing installation, preserve its `data/` directory and current key/token while replacing the Compose definition. Do not run `docker compose down --volumes`; Compose may recreate the existing `beszel-agent` container briefly during the migration. Verify the Hub connection and host metrics after deployment. GCP container metrics will intentionally disappear.

## Local validation

```bash
docker compose --env-file .env.example config --quiet
pnpm lint:compose
```
