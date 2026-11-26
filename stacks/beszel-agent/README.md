# Beszel Agent

This Compose project runs an outbound-only agent that reports host and Docker metrics to a [Beszel Hub](../beszel-hub/README.md). For NVIDIA GPU metrics, see the [NVIDIA agent](../beszel-agent-nvidia/README.md).

The agent uses host networking for host interface metrics. `DISABLE_SSH=true` turns off its inbound SSH listener, and `BESZEL_HUB_URL` selects the Hub for its outbound WebSocket connection.

Container monitoring uses a direct Docker socket mount. The `:ro` mount protects the socket path from filesystem writes. Docker API access still carries the Docker daemon's privileges.

## Arcane Git Sync

Create a [Pull sync](https://getarcane.app/docs/docker/git-sync#create-a-git-synced-project) on the remote Agent that runs Beszel. Set the sync and Compose project name to `beszel-agent` and the Compose File Path to `stacks/beszel-agent/compose.yaml`. Supply `BESZEL_HUB_URL`, `BESZEL_AGENT_KEY`, and `BESZEL_AGENT_TOKEN_PATH` in the sync environment. The first pull runs when you save the sync. Turn off the previous controller's automatic deployment for this project before saving.

For an existing agent, reuse its Hub registration and point `BESZEL_AGENT_TOKEN_PATH` at the current token file on the target host. For a new agent, register it with **Add System** in Beszel and store its token as one line in a private file with mode `0600`. Arcane receives the path, and Beszel reads the token from the Compose secret through `TOKEN_FILE`. For manual deployment, set the same variables in a local `.env` beside `compose.yaml` and run `docker compose up -d`.

## Verify

Check that the Hub receives fresh host and Docker metrics. Keep the `beszel-agent-data` named volume and its associated system registration across deployments.

## Local validation

```bash
BESZEL_AGENT_KEY=placeholder docker compose --env-file .env.example config --quiet
pnpm lint:compose
```
