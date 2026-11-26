# Beszel Hub

This project runs the [Beszel Hub](https://beszel.dev/guide/getting-started). It serves HTTP at `beszel-hub:8090` on the external `caddy-network`. Configure your HTTPS reverse proxy to forward requests to that address. The [GCP Caddy stack](../../compose/caddy-gcp/README.md) creates the shared network when used as the proxy.

## Deploy

Create an [Arcane Pull sync](https://getarcane.app/docs/docker/git-sync#create-a-git-synced-project) on the host running the Hub. Use `beszel-hub` as the sync and Compose project name and `stacks/beszel-hub/compose.yaml` as the Compose File Path. Set `BESZEL_APP_URL` in the sync environment to the Hub's HTTPS URL, for example `https://beszel.example.com`. For direct recovery with Docker Compose, put the same value in a host-local `.env` and run `docker compose up -d --wait`.

The `beszel-data` named volume stores the database, account information, Hub keys, and application settings. Preserve the volume across deployments and keep its contents outside Git.

Open the HTTPS URL to create the initial administrator account on a fresh deployment. Keep account credentials and agent tokens outside Git.

## Verify

Verify the Hub through the reverse proxy with certificate validation enabled. Replace `beszel.example.com` with your domain.

```bash
curl --fail https://beszel.example.com/api/health
```

After moving an existing Hub, verify login and check that the existing systems are still registered and receive fresh metrics.

For local Compose validation:

```bash
BESZEL_APP_URL=https://beszel.example.com docker compose config --quiet
```
