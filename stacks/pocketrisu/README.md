# PocketRisu

[PocketRisu](https://github.com/PocketRisu/PocketRisu) is an AI character and roleplay chat application derived from RisuAI. It stores chats on the server and uses a separate model provider.

## Deployment

- Compose project and container: `pocketrisu`.
- Image: `ghcr.io/pocketrisu/pocketrisu:v1.17.0`.
- Volume: `pocketrisu-data` mounted at `/app/save`. Compose derives the Docker volume name `pocketrisu_pocketrisu-data` from the project name and volume key. Keep the project name when updating to reuse the same volume.
- The external Docker network `caddy-network` must exist. Configure your HTTPS reverse proxy on that network to forward to `pocketrisu:6001`. Compose publishes no host port.

In Arcane, create a [Pull sync](https://getarcane.app/docs/docker/git-sync#create-a-git-synced-project) on the target host. Use `pocketrisu` as the sync and Compose project name and `stacks/pocketrisu/compose.yaml` as the Compose File Path. For manual deployment, run these commands from this directory.

```sh
docker compose config --quiet
docker compose up -d --wait
docker compose ps
```

The stack requires no `.env` file. Configure application credentials and provider settings through the UI.

## Authentication and privacy

For a fresh instance, set a unique application password through a trusted connection before giving other clients access. The login page and static manifest can load before sign-in. Verify that private chats require authentication.

The data volume and logs can contain credentials, session data, and private conversations. Keep them and their backups outside Git.

## Persistent data and backups

The complete `/app/save` directory is the persistence boundary. It includes the
main SQLite database, auxiliary log and job databases, SQLite WAL/SHM files,
assets, and authentication files. Never replace the volume with an empty one or
use `docker compose down --volumes` for routine maintenance.

Application snapshots in the same volume are useful for recovery from some
application changes, but are not an independent backup. UI exports are useful
for data portability and should not be assumed to include every server file,
credential, session, or log.

For a complete backup, schedule a short outage, stop the service with
`docker compose stop pocketrisu`, archive the entire named volume to private
storage outside the repository, then start it with
`docker compose start pocketrisu`. Ensure the backup succeeded before making a risky change. Do not
copy a live SQLite `.db` alone: committed data can still be in its WAL. Protect
backup permissions and maintain a copy separate from this host. Restoring must
be done while the service is stopped and must preserve the complete data set.

## Updates and checks

Take a complete backup before changing the image tag in `compose.yaml`. Use **Sync from Git** in Arcane to apply the updated definition, or use these commands for a manual deployment.

```sh
docker compose pull pocketrisu
docker compose up -d --wait pocketrisu
docker compose ps
docker compose logs --tail 50 pocketrisu
```

The Compose healthcheck verifies the static manifest inside the container. To check the reverse proxy, substitute your domain in this example:

```sh
curl --fail --silent --show-error --output /dev/null https://pocketrisu.example.com/manifest.json
```

In the browser, verify sign-in, access to saved characters and chats, and a new model response. Keep the matching backup until verification is complete. A storage migration can require restoring that backup when rolling back the image.

## Upstream references

- [PocketRisu v1.17.0 release notes](https://github.com/PocketRisu/PocketRisu/releases/tag/v1.17.0)
