# Arcane Agent

Run this stack on a remote Docker host that should connect to [Arcane Manager](../arcane/README.md). The agent uses the host Docker socket and opens an outbound connection to the Manager over HTTPS. It publishes no ports. See the [official agent setup](https://getarcane.app/docs/remote/agents).

## Bootstrap with pyinfra

Save the remote target in a [private Python inventory](../../pyinfra/README.md#compose-stacks). Configure the alias's login and identity in the controller's `~/.ssh/config`.

```python
oci = [("cloud-example-01", {"stacks": {"arcane-agent": {"bootstrap": True}}})]
```

The deploy requires an explicit stack selection and uses the stack owner's `~/compose/arcane-agent/` directory.

In Manager, use **Agents → Add Agent** to generate a single-use enrollment token for the host. Put only the token in `.env.arcane-agent-token` in the target project directory. Keep the directory at mode `0700` and the token file at mode `0644` so the unprivileged container process can read its mounted secret. Keep the token and Manager URL outside Git.

Copy `.env.example` to a private controller file with mode `0600` and set `ARCANE_MANAGER_API_URL` to the reachable HTTPS address. Run this from `pyinfra/`, substituting your inventory, host, and environment file.

```sh
uv run pyinfra "$HOME/.config/homelab/arcane-agents.py" tasks.stacks.apply \
  --limit cloud-example-01 \
  --data stack=arcane-agent --data stack_env_file=/path/to/private.env --serial --yes
```

`stack_env_file` seeds the target `.env` once. For subsequent applies, omit that argument and leave the target `.env` and token file in place. The agent stores the issued key in `/app/data` on the named volume and reuses it on restart.

## Verify and recover

Check that the host shows **Online** in Manager and its Docker containers are visible. To verify reconnection, restart `arcane-agent` with Docker Compose on the target host and check that the same Agent returns to **Online**. Keep the named volume when recreating the container. If its state is lost, [re-enroll the existing Agent](https://getarcane.app/docs/remote/agents#re-enroll-an-agent) with a new token to retain its identity in Manager.
