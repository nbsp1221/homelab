# Komodo

This project runs Komodo Core, MongoDB, and local Periphery on one host. Start, upgrade, and recover Komodo from the host with Docker Compose. The configuration is based on the [official MongoDB Compose example](https://github.com/moghtech/komodo/blob/v2.3.4/compose/mongo.compose.yaml).

## Install

Copy `compose/komodo/compose.yaml` from the homelab checkout to the host's deployment directory, such as `~/compose/komodo/`. For a fresh install, use `.env.example` to create `.env` next to the deployed Compose file with permissions `0600`. Set `KOMODO_HOST` to the HTTPS address configured in Caddy. Set the database and initial administrator passwords, JWT secret, and webhook secret to independently generated values. Keep the existing `.env` when updating the deployed Compose file.

Caddy and Core share the existing `caddy-network` network. Caddy forwards to `komodo-core:9120` so Core does not publish a host port. Local Periphery connects to Core on the project network. The Core and Periphery image tags follow the official `:2` setting. MongoDB uses `mongo:9.0` to keep upgrades within that release series until the tag is changed explicitly.

Run these commands from the deployment directory:

```sh
docker compose config --quiet
docker compose pull
docker compose up -d
docker compose ps
```

Check that MongoDB and Core report healthy. The MongoDB probe checks command responsiveness, and the Core probe checks HTTP on `/version`. Sign in through Caddy and verify that the `Local` server reports `Ok` and lists its containers.

## State and recovery

Periphery uses `/etc/komodo` at the same path inside the container and on the host. Core and local Periphery share the `komodo_keys` Docker volume. MongoDB uses the `komodo_mongo-data` and `komodo_mongo-config` volumes. The official scheduled database backup writes to `/etc/komodo/backups`. Retain the database backup, connection keys, and private environment file together for recovery. Follow [Komodo's database restore procedure](https://komo.do/docs/setup/backup#restore) when restoring a backup.

Periphery prepares managed Stack files under its working directory on the target host. Each service's Compose file controls where its persistent data is stored. To recover the Komodo installation itself, place the saved `.env` and the matching `compose.yaml` in the deployment directory before running Docker Compose.
