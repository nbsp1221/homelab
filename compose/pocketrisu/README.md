# PocketRisu

[PocketRisu](https://github.com/PocketRisu/PocketRisu) is a GPL-3.0 AI
character and roleplay chat application derived from RisuAI. It connects to
external AI providers or a separately operated local model server; this Compose
project does not run a language model. Generation runs on the server, and chat
state is shared between browsers through server storage.

## Deployment

- Canonical file: `compose/pocketrisu/compose.yaml`.
- Compose project and container: `pocketrisu`.
- Official image pinned to `ghcr.io/pocketrisu/pocketrisu:v1.13.0`.
- Existing named volume: `pocketrisu_pocketrisu-data`, mounted at `/app/save`.
  Its explicit name preserves the current data when the project directory moves.
- Port `6001` is available only on the external `caddy-network`; there is no
  published host port. The network must already exist.
- Caddy provides HTTPS and the HTTP reverse proxy. The hostname currently
  resolves to this server's Tailscale IPv4 and IPv6 addresses, so the client needs
  a working Tailscale connection. Public DNS records do not imply public
  internet reachability. No Cloudflare Tunnel route is established by this
  Compose project; the Caddy deployment manages the actual hostname.

Run these commands from this directory:

```sh
docker compose config --quiet
docker compose up -d --wait
docker compose ps
```

The proxy target is `pocketrisu:6001`. Do not enable the application's additional
Quick Tunnel for this deployment. No `.env` file is required by this Compose
configuration; application credentials and provider settings are managed in the
application and its private data volume.

## Authentication and privacy

For a fresh instance, set the application password through a trusted connection
before making it accessible to other clients. The existing instance already
has a password.
Unauthenticated access to the frontend and its static manifest is expected; it
does not demonstrate access to private chats. Protected API requests must remain
blocked without authentication. `/api/test_auth` reports `incorrect` for an
unauthenticated client; some protected APIs return HTTP 400 rather than 401.

Use a strong, unique password. The application stores password verification data,
JWT signing material, and sessions inside `/app/save`. The volume also contains
characters, chats, assets, provider settings, generation jobs, and request logs.
Request bodies and responses can contain private conversations even where
credential fields are redacted. Keep the volume, exports, and backups private and
outside this repository. Requests sent to an external model provider are also
subject to that provider's data handling.

The upstream image runs as root inside the container. This deployment does not
use privileged mode, mount the Docker socket, or publish a host port. Changing the
container user or making the root filesystem read-only requires separate testing
of SQLite writes and upstream runtime behavior. Password strength and Tailscale access
policy are not verified by this Compose configuration.

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

Change the pinned image tag deliberately. Before an update, record the current
tag and take a complete backup, then run:

```sh
docker compose pull pocketrisu
docker compose up -d --wait pocketrisu
docker compose ps
docker compose logs --tail 50 pocketrisu
```

Inspect logs privately; do not paste conversations or credentials into issues.
After an update, verify login, existing characters/chats, and generation through
the UI. The healthcheck only verifies that the static manifest responds; it does
not verify authentication, SQLite integrity, or successful model generation.
If an update migrates storage, reverting the image alone may not be sufficient;
retain the matching full backup throughout verification. A temporary change
backup can be removed after successful verification; independent disaster
recovery backups are a separate policy.

As of 2026-10-01, the upstream release is
[v1.13.0](https://github.com/PocketRisu/PocketRisu/releases/tag/v1.13.0).
This deployment was updated from v1.12.0 after a complete stopped-volume backup.
SQLite integrity, chat and asset preservation, login and protected API access,
and HTTPS availability over Tailscale were checked. The temporary backup was removed after
these checks. Full browser interaction and a new model generation were not tested.
The previous v1.12.0 deployment logged a frontend error involving
`null.displayData`; release notes do not establish that v1.13.0 fixes that exact
error. A healthy container alone does not demonstrate that the UI issue is fixed.

## Upstream references

- [Installation (deployed version)](https://github.com/PocketRisu/PocketRisu/blob/v1.13.0/docs/en/install.md)
- [Remote access (deployed version)](https://github.com/PocketRisu/PocketRisu/blob/v1.13.0/docs/en/remote.md)
- [Official Compose example](https://github.com/PocketRisu/PocketRisu/blob/v1.13.0/docker-compose.yml)
- [Official Dockerfile](https://github.com/PocketRisu/PocketRisu/blob/v1.13.0/Dockerfile)
