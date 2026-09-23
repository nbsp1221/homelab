# Beszel cloud agent

This standalone Compose project runs an outbound-only Beszel agent on a cloud host. The Hub and NVIDIA-specific main-host agent remain in [`beszel/`](../../beszel/README.md). Placement and Hub URLs for the GCP and two OCI agents are declared in their respective [`hosts/`](../../hosts/README.md) definitions; do not deploy a second agent on any of these hosts.

The agent uses host networking for host interface metrics, but `DISABLE_SSH=true` disables its inbound SSH listener. It keeps the existing outbound WebSocket connection to the Hub at `https://beszel.retn0.dev`.

Docker container monitoring keeps the cloud hosts' existing direct `/var/run/docker.sock:ro` mount. This is the smallest change that preserves its current metrics and avoids adding a proxy service. The `:ro` mount protects the socket path from filesystem writes, but it does not restrict Docker API requests; access to the Docker daemon remains highly privileged. If that risk becomes unacceptable, use a restricted socket proxy like the main host rather than assuming `:ro` makes the API read-only.

## Host prerequisites

- Docker Engine and Compose, already installed by the `pyinfra` baseline.
- Connectivity to the existing private `https://beszel.retn0.dev` Hub endpoint. It resolves to a Tailscale address from the main and cloud hosts; this deployment does not change the Hub route or require Tailscale Serve.
- The Beszel Hub public key and a token issued for this specific system through **Add System**. Keep both in the host-local `.env`, not in Git. Do not use a Universal Token for these agents.

## First deployment

Add each host as a separate system in the Beszel Hub and copy the generated public key and system-specific token into that host's `.env` using `.env.example` as a guide. Restrict the file to the operator account. The [pyinfra executor](../../deploy/pyinfra/README.md) copies `compose.yaml` to `/opt/stacks/beszel-agent` when explicitly invoked. Keep `./data` persistent: Beszel stores the agent identity there. The Hub URL comes from the host definition and is synchronized into the target's `.env`, so normal `docker compose` commands work there too.

```bash
cd /opt/stacks/beszel-agent
chmod 600 .env
docker compose ps
docker compose exec -T beszel-agent /agent health
```

The Hub should show one online entry for the host. Do not create a duplicate system record for an existing agent.

For an existing installation, preserve its `data/` directory and current key/token while replacing the Compose definition. Do not run `docker compose down --volumes`; Compose may recreate the existing `beszel-agent` container briefly during the migration. Verify the Hub connection, host metrics, and Docker metrics after deployment.

## Local validation

```bash
BESZEL_HUB_URL=https://beszel.retn0.dev \
  docker compose --env-file .env.example config --quiet
pnpm lint:compose
```
