# Beszel Agent

This Compose project runs an outbound-only agent that reports host and Docker metrics to a [Beszel Hub](../beszel-hub/README.md). For NVIDIA GPU metrics, see the [NVIDIA agent](../beszel-agent-nvidia/README.md).

The agent uses host networking for host interface metrics. `DISABLE_SSH=true` turns off its inbound SSH listener, and `BESZEL_HUB_URL` selects the Hub for its outbound WebSocket connection.

Container monitoring uses a direct Docker socket mount. The `:ro` mount protects the socket path from filesystem writes. Docker API access still carries the Docker daemon's privileges.

## Komodo

Select the target server and the Repo containing this definition. For a server named `host-01`, use the Stack name `beszel-agent-host-01` and the run directory `compose/beszel-agent`. Set Project Name to `beszel-agent` to match the Compose project and supply `BESZEL_HUB_URL` and `BESZEL_AGENT_KEY` in the Stack environment. Agents that report to the same Hub use the same URL and Hub public key.

Register the host with **Add System** in Beszel. On the target host, store its token as one line in the file identified by `secrets.beszel_agent_token.file` in [`compose.yaml`](compose.yaml). Use mode `600` and keep the file outside Git. The agent reads the mounted secret through `TOKEN_FILE`. For manual deployment, set the remaining variables in a local `.env` beside the Compose file and run `docker compose up -d`.

## Verify

Check that the Hub receives fresh host and Docker metrics. Keep the `beszel-agent-data` named volume and its associated system registration across deployments.

## Local validation

```bash
BESZEL_HUB_URL=https://beszel.example.com BESZEL_AGENT_KEY=placeholder \
  docker compose config --quiet
pnpm lint:compose
```
