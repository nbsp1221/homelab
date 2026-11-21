# Beszel Hub

This project runs the [Beszel Hub](https://beszel.dev/guide/getting-started). It serves HTTP at `beszel-hub:8090` on the external `caddy-network`. Configure your HTTPS reverse proxy to forward requests to that address. The [GCP Caddy stack](../caddy-gcp/README.md) creates the shared network when used as the proxy.

## Deploy

Set `BESZEL_APP_URL` to the Hub's HTTPS URL, for example `https://beszel.example.com`. For Komodo, select the target server and Repo, use `compose/beszel-hub` as the run directory, and set the variable in the Stack environment. For manual Compose deployment, set it in a local `.env` beside `compose.yaml` and run `docker compose up -d --wait`.

For pyinfra, set the variable in the [host definition](../../hosts/README.md) and select `beszel-hub` when [applying the stack](../../deploy/pyinfra/README.md#compose-stacks).

The `beszel-data` named volume stores the database, account information, Hub keys, and application settings. Preserve the volume across deployments and keep its contents outside Git.

Open the HTTPS URL to create the initial administrator account on a fresh deployment. Keep account credentials and agent tokens outside Git.

## Verify

Verify the Hub through the reverse proxy with certificate validation enabled. Replace `beszel.example.com` with your domain.

```bash
curl --fail https://beszel.example.com/api/health
```

For local Compose validation:

```bash
BESZEL_APP_URL=https://beszel.example.com docker compose config --quiet
```
