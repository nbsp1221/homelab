# Arcane Agent

Run this stack on a remote Docker host that should connect to [Arcane Manager](../arcane/README.md). The agent uses the host Docker socket and opens an outbound connection to the Manager over HTTPS. It publishes no ports. See the [official agent setup](https://getarcane.app/docs/remote/agents).

## Bootstrap with pyinfra

In a private host inventory, assign `arcane-agent: {bootstrap: true}` under `stacks` for the selected host. Use that inventory via `HOMELAB_HOSTS_DIR`. The deploy runs only when the stack is explicitly selected and places the project in the SSH user's `~/compose/arcane-agent/` directory.

In Manager, use **Agents → Add Agent** to generate a single-use enrollment token for the host. Put only the token in `.env.arcane-agent-token` in the target project directory. Keep the directory at mode `0700` and the token file at mode `0644` so the unprivileged container process can read its mounted secret. Keep the token and Manager URL outside Git.

Copy `.env.example` to a private controller file with mode `0600` and set `ARCANE_MANAGER_API_URL` to the reachable HTTPS address. Run this from `deploy/pyinfra/`, substituting your inventory directory, host, and environment file.

```sh
HOMELAB_HOSTS_DIR="$HOME/.config/homelab/hosts" uv run pyinfra \
  inventories/production.py deploys/stacks.py --limit cloud-example-01 \
  --data stack=arcane-agent --data stack_env_file=/path/to/private.env --serial --yes
```

`stack_env_file` seeds the target `.env` once. For subsequent applies, omit that argument and leave the target `.env` and token file in place. The agent stores the issued key in `/app/data` on the named volume and reuses it on restart.

## Verify and recover

Check that the host shows **Online** in Manager and its Docker containers are visible. To verify reconnection, restart `arcane-agent` with Docker Compose on the target host and check that the same Agent returns to **Online**. Keep the named volume when recreating the container. If its state is lost, [re-enroll the existing Agent](https://getarcane.app/docs/remote/agents#re-enroll-an-agent) with a new token to retain its identity in Manager.
