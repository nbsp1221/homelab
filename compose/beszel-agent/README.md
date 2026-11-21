# Beszel cloud agent

This Compose project runs an outbound-only Beszel agent on the GCP and OCI hosts. The agents report to the [GCP Hub](../beszel-hub/README.md). The main host uses the [NVIDIA agent definition](../beszel-agent-nvidia/README.md).

The agent uses host networking for host interface metrics. `DISABLE_SSH=true` turns off its inbound SSH listener, and `BESZEL_HUB_URL` selects the Hub for its outbound WebSocket connection.

Docker container monitoring keeps the cloud hosts' existing direct `/var/run/docker.sock:ro` mount. This is the smallest change that preserves its current metrics and avoids adding a proxy service. The `:ro` mount protects the socket path from filesystem writes, but it does not restrict Docker API requests; access to the Docker daemon remains highly privileged. If that risk becomes unacceptable, use a restricted socket proxy like the main host rather than assuming `:ro` makes the API read-only.

## Komodo

Create a Stack named `beszel-agent-<server>` on each target server. Use the `homelab` Repo, `compose/beszel-agent` as the run directory, and `beszel-agent` as the Project Name. Set `BESZEL_HUB_URL` and `BESZEL_AGENT_KEY` in the Stack environment. Agents that report to the same Hub use the same URL and Hub public key.

Store each system's token as a single line in `/etc/komodo/secrets/beszel-agent.token` on its server with mode `600`. Compose mounts this file and the agent reads it through `TOKEN_FILE`. The same path works for manual Compose deployments with the remaining variables in a local `.env` beside the Compose file.

## Migration

For each existing agent, keep its current system registration, token, and data. Prepare that token in the file above and copy `/opt/stacks/beszel-agent/data/` into the `beszel-agent_beszel-agent-data` Docker volume, including the fingerprint. Keep the old Compose project files and data on the host for rollback.

After preparing the token and volume, take down the old project using its Compose file and deploy the Stack in Komodo. Verify that the new agent is healthy and the existing system in the Hub receives fresh host and Docker metrics.

For a new host, register it through **Add System** in the Hub and use the token issued for that system.

## Local validation

```bash
BESZEL_HUB_URL=https://beszel.example.com BESZEL_AGENT_KEY=placeholder \
  docker compose config --quiet
pnpm lint:compose
```
