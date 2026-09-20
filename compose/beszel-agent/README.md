# Beszel cloud agent

This standalone Compose project runs an outbound-only Beszel agent on a cloud host. The Hub and NVIDIA-specific main-host agent remain in [`beszel/`](../../beszel/README.md). Its GCP placement and Hub URL are declared in [`hosts/retn0-srv-gcp-01/host.yaml`](../../hosts/retn0-srv-gcp-01/host.yaml); do not deploy a second agent on that host.

The agent uses host networking for host interface metrics, but `DISABLE_SSH=true` disables its inbound SSH listener. It keeps the existing outbound WebSocket connection to the Hub at `https://beszel.retn0.dev`.

Docker container monitoring keeps the GCP host's existing direct `/var/run/docker.sock:ro` mount. This is the smallest change that preserves its current metrics and avoids adding a proxy service. The `:ro` mount protects the socket path from filesystem writes, but it does not restrict Docker API requests; access to the Docker daemon remains highly privileged. If that risk becomes unacceptable, use a restricted socket proxy like the main host rather than assuming `:ro` makes the API read-only.

## Host prerequisites

- Docker Engine and Compose, already installed by the `pyinfra` baseline.
- Connectivity to the existing private `https://beszel.retn0.dev` Hub endpoint. It currently resolves to a Tailscale address from both the main and GCP hosts; this deployment does not change the Hub route or require Tailscale Serve.
- A Beszel Hub public key and universal token. Keep both in the host-local `.env`, not in Git.

## First deployment

The [pyinfra executor](../../deploy/pyinfra/README.md) copies `compose.yaml` to `/opt/stacks/beszel-agent` when explicitly invoked. Set the target's `.env` from `.env.example` with the real key and token, and restrict it to the operator account. Keep `./data` persistent: Beszel stores the agent identity there. The Hub URL is supplied from the host definition, not from `.env.example`.

```bash
cd /opt/stacks/beszel-agent
chmod 600 .env
docker compose ps
docker compose exec -T beszel-agent /agent health
```

The Hub should show one online entry for the host. Do not create another Hub system record when a universal token has already registered this agent.

For an existing installation, preserve its `data/` directory and current key/token while replacing the Compose definition. Do not run `docker compose down --volumes`; Compose may recreate the existing `beszel-agent` container briefly during the migration. Verify the Hub connection, host metrics, and Docker metrics after deployment.

## Local validation

```bash
BESZEL_HUB_URL=https://beszel.retn0.dev \
  docker compose --env-file .env.example config --quiet
pnpm lint:compose
```
