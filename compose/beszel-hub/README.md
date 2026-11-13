# Beszel Hub

This project runs the [Beszel Hub](https://beszel.dev/guide/getting-started) using the upstream `henrygd/beszel:0.21.0` image, matching the existing agents. It joins the external `caddy-network` and serves HTTP on container port 8090 without publishing a host port. On GCP, `caddy-gcp` creates this network and proxies `https://beszel.retn0.dev` to the Hub.

`hosts/<hostname>/host.yaml` sets `BESZEL_APP_URL`. pyinfra writes this non-secret value to the host-local `.env`. The `beszel-hub_beszel-data` volume stores the database, account information, Hub keys, and application settings. Preserve this volume across deployments and keep its contents outside Git.

Deploy `caddy-gcp` first, then this stack, from `deploy/pyinfra`:

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --data stack=beszel-hub --dry --serial
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --data stack=beszel-hub --serial --yes
```

Open the HTTPS URL to create the initial administrator account using Beszel's setup screen. Account credentials and agent tokens belong in the Hub or host-local secret files, never in Compose or host definitions. The main-host, GCP, and both OCI agents are registered in this Hub, each with its own system-specific token. The old main-host Hub and its database have been removed; existing history is not copied into this Hub. The separate desktop will be registered later.

Verify the Hub through Caddy with certificate validation enabled:

```bash
curl --noproxy '*' --fail https://beszel.retn0.dev/api/health
```

For local Compose validation:

```bash
BESZEL_APP_URL=https://beszel.example.com docker compose config --quiet
```
