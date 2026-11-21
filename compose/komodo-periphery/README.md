# Komodo Periphery

This stack connects a Docker host to Komodo Core with an outbound connection using the [official Periphery container setup](https://komo.do/docs/setup/connect-servers#container). It publishes no host ports.

Run pyinfra from `deploy/pyinfra` after the controller can reach the target over SSH and the target has Docker and Compose. In the target's `host.yaml`, assign `komodo-periphery` with `bootstrap: true` and set `PERIPHERY_CORE_ADDRESS` and `PERIPHERY_CONNECT_AS` in its environment. For example, use `https://komodo.example.com` for Core and `host-01` for the server name.

## First deployment

Preview the target before issuing an onboarding key. Replace `host-01` in these commands with its inventory name.

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit host-01 --data stack=komodo-periphery --dry --serial
```

Create a server onboarding key in Komodo. On the controller, create a private file with mode `600` outside the repository containing one line, `PERIPHERY_ONBOARDING_KEY=<key>`. Pass its absolute path only when initially seeding the target `.env`.

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit host-01 --data stack=komodo-periphery \
  --data stack_env_file=/absolute/path/to/private.env --serial --yes
```

Open **Servers** in Komodo, confirm the target is `OK`, and check that its **Docker** tab loads the container list.

After each host connects, remove the `PERIPHERY_ONBOARDING_KEY` line from its `.env` and rerun the same apply command without `stack_env_file`. This applies the updated environment and uses the stored keys for reconnection. Confirm the server returns to `OK`. Keep the `keys` volume across updates and container recreation.
