# Komodo Periphery

This stack connects each GCP and OCI Docker host to the existing Komodo Core. It uses the [official Periphery container setup](https://komo.do/docs/setup/connect-servers#container) with an outbound connection. It publishes no host ports.

Run pyinfra from `deploy/pyinfra` on the controller after the target can be reached over Tailscale SSH and its Docker baseline is applied. Each `host.yaml` provides the Core URL and the name that appears in Komodo. pyinfra places `compose.yaml` and `.env` in `~/compose/komodo-periphery` on the target. Periphery stores deployment files under `/etc/komodo` and connection keys in the `komodo-periphery_keys` Docker volume.

## First deployment

Preview GCP first. This also works before an onboarding key has been issued.

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --data stack=komodo-periphery --dry --serial
```

Create a server onboarding key in Komodo. On the controller, create a private file with mode `600` outside the repository containing one line, `PERIPHERY_ONBOARDING_KEY=<key>`. Pass its absolute path only when initially seeding the target `.env`.

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --data stack=komodo-periphery \
  --data stack_env_file=/absolute/path/to/private.env --serial --yes
```

Open **Servers** in Komodo, confirm `retn0-srv-gcp-01` is `OK`, and check that its Docker tab lists the existing `beszel-hub` container. Repeat for `retn0-srv-oci-01` and `retn0-srv-oci-02` by changing `--limit`.

After each host connects, remove the `PERIPHERY_ONBOARDING_KEY` line from its `.env` and rerun the same apply command without `stack_env_file`. This applies the updated environment and uses the stored keys for reconnection. Confirm the server returns to `OK`. Keep the `keys` volume across updates and container recreation.
