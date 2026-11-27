# Arcane Agent

Run this stack on a remote Docker host that should connect to [Arcane Manager](../arcane/README.md). The agent uses the host Docker socket and opens an outbound connection to the Manager over HTTPS. It publishes no ports. See the [official agent setup](https://getarcane.app/docs/remote/agents).

## Install

Copy `compose.yaml` and `.env.example` to a private deployment directory on the Agent host, such as `~/compose/arcane-agent/` with mode `0700`. Create a local `.env` from the example, set `ARCANE_MANAGER_API_URL` to the Manager's reachable HTTPS address, and set the file mode to `0600`.

In Manager, use **Agents → Add Agent** to generate a single-use enrollment token for the host. Put only the token in `.env.arcane-agent-token` in the deployment directory. Use mode `0644` on the token file so the unprivileged container process can read its mounted secret, and keep the parent directory private. Keep the token and Manager URL outside Git.

Run from the deployment directory.

```sh
docker compose config --quiet
docker compose pull
docker compose up -d --wait --wait-timeout 120
```

Keep the host-local environment and token files on subsequent applies. The Agent stores the issued key in the named volume and reuses it on restart.

## Verify and recover

Check that the host shows **Online** in Manager and its Docker containers are visible. To verify reconnection, restart `arcane-agent` with Docker Compose on the target host and check that the same Agent returns to **Online**. Reapply from the same deployment directory and keep the named volume when recreating the container. If its state is lost, [re-enroll the existing Agent](https://getarcane.app/docs/remote/agents#re-enroll-an-agent) with a new token to retain its identity in Manager.
