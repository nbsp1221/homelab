# Arcane

This project runs Arcane Manager on the management host using the [official Docker Compose installation](https://getarcane.app/docs/get-started/installation). Manager monitors and manages the local Docker engine through its socket. Run an [Arcane Agent](../arcane-agent/README.md) on each other Docker host when adding remote environments. Bootstrap and recover the Manager and Agents with Docker Compose on their hosts.

## Install

Copy `compose.yaml` and `.env.example` to a deployment directory on the management host, such as `~/compose/arcane/`. On first install, use `.env.example` to create a private `.env` with mode `0600`. Generate `ARCANE_ENCRYPTION_KEY` with `openssl rand -hex 32`. Keep the existing `.env` when upgrading.

Arcane joins the external `caddy-network` network. For HTTPS, attach Caddy to that network, forward the site to `arcane:3552`, and set `ARCANE_APP_URL` in `.env` to the URL opened by users, such as `https://arcane.example.com`. Caddy forwards the WebSocket connections that Arcane uses for live updates. See the [Arcane reverse proxy guide](https://getarcane.app/docs/networking/reverse-proxy).

On a host that runs this repository's [Caddy stack](../../compose/caddy-gcp/README.md#install-and-recover), install that stack first so its Compose project creates `caddy-network`. On a host where you manage the network separately, create it once if needed.

```sh
docker network inspect caddy-network >/dev/null 2>&1 || docker network create caddy-network
```

Run from the Manager deployment directory.

```sh
docker compose config --quiet &&
  docker compose pull &&
  docker compose up -d --wait --wait-timeout 120
```

Open the URL configured in `ARCANE_APP_URL`. For a local install using the default `http://localhost:3552`, forward the loopback port over SSH to access it from another machine.

```sh
ssh -N -L 3552:127.0.0.1:3552 admin@manager.example.com
```

Sign in as `arcane` and change the generated initial password when prompted. Read it from the management host's deployment directory.

```sh
docker compose cp arcane:/app/data/initial-admin-password - | tar -xO
```

## Verify

Run `docker compose ps` and check that Manager is healthy. In Arcane, confirm the local environment is online, its container list includes an existing host container, and its Dashboard shows host CPU and memory. Compare the container list with `docker ps` on the deployment host.

## State and recovery

Reapply from the same deployment directory with the original project name, `.env`, and named volume. Restore a lost encryption key from the backup before starting the Manager with its existing data.

The `arcane_arcane-data` volume holds the Manager database, configuration, and default `/app/data/projects` directory. Arcane places each new Git-synced Compose project in this directory on the selected environment. See [where projects live](https://getarcane.app/docs/docker/projects#where-projects-live).

Back up the volume and the private `.env` containing the encryption key together. Keep the key available when restoring the database.

## Adopt an existing stack

Confirm the existing Compose project name, named volumes, bind mounts, and host-local environment on the target Docker engine. Secure a rollback copy of the Compose files and the necessary settings. Keep the project name and volume names when creating the Arcane Pull sync.

Disable the previous controller's deploy automation for that stack before saving the sync. Arcane runs the first pull immediately and may redeploy a running project. Verify the application through its normal endpoint, including that its data and integrations still work. Switch one host or workload at a time and enable automatic sync after verification.

Keep the previous deployment files available during the rollout. To roll back, pause the Arcane sync and apply the previous Compose files with the original project name and volumes. Preserve volumes during both cutover and rollback.
