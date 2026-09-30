# Multica

A Docker Compose deployment of Multica using the official backend and frontend images, PostgreSQL with pgvector, and persistent volumes for database and uploaded data.

The frontend and backend join the external `caddy-network` so a reverse proxy can expose them without publishing application ports on the host.

## Network model

Multica's backend is a client-facing product endpoint, not only an internal admin API.
The CLI, agent daemons and runtimes, integrations, readiness checks, and WebSocket task channel must be able to reach it.

Use HTTPS endpoints that are reachable by every intended client.
For runtimes outside the private network this normally means a public HTTPS API protected by Multica's authentication.
The web app may share an origin with the API or use a separate hostname; configure the environment and reverse proxy consistently.

For a same-origin browser deployment:

- proxy `/api`, `/auth`, and `/uploads` through the frontend;
- proxy `/ws` and `/ws/*` to the backend;
- leave `COOKIE_DOMAIN` empty;
- keep `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_WS_URL` empty.

If a separate API hostname is used, route it directly to `backend:8080` and set `MULTICA_PUBLIC_URL` to that HTTPS URL.
CLI and daemon clients use this API hostname, including `/health` and `/api/daemon/ws`.
Browser requests still go through the frontend; leave `CORS_ALLOWED_ORIGINS` and `COOKIE_DOMAIN` empty in this layout.
If browsers instead call the API hostname directly, follow the upstream cross-origin CORS and cookie configuration.
For a single-hostname layout, also proxy `/health` and `/api/daemon/ws` directly to the backend; the frontend cannot forward WebSocket upgrades.
Do not add a network allowlist that prevents registered remote runtimes or CLI clients from reaching the backend.

## Initial setup

Run from the repository root, then create a private environment file and replace every placeholder:

```bash
cd compose/multica
cp .env.example .env
chmod 600 .env
```

Generate independent credentials:

```bash
openssl rand -hex 32      # JWT_SECRET
openssl rand -hex 24      # POSTGRES_PASSWORD
openssl rand -base64 32   # MULTICA_VCS_SECRET_KEY
```

At minimum, set the public frontend origin and review the related URL, cookie, CORS, signup, and email-delivery settings in `.env.example`.
Signup is closed by default. Before creating the first account, set `ALLOWED_EMAILS` to the operator email address.
Existing users can sign in with `ALLOW_SIGNUP=false`.

Validate and start:

```bash
docker compose config -q
docker compose pull
docker compose up -d --wait
docker compose ps
```

After editing `.env`, use `docker compose up -d` to recreate affected containers.
A plain restart does not reload Compose environment values.

## Verify

Check PostgreSQL from inside the project:

```bash
docker compose exec -T postgres pg_isready -U multica -d multica
```

Check both public surfaces through the reverse proxy:

```bash
curl -fsS https://api.example.com/readyz
curl -fsS https://multica.example.com/login >/dev/null
```

Also verify CLI login and an agent runtime from a machine outside the server; that catches API reachability and WebSocket proxy errors that a local health check cannot detect.

## Production bootstrap

Keep `APP_ENV=production` and leave `MULTICA_DEV_VERIFICATION_CODE` empty.
Set up an email provider for login codes.

After creating the initial workspace:

1. Set `DISABLE_WORKSPACE_CREATION=true` if users should not create more workspaces.
2. Set `ALLOW_SIGNUP=false` if no additional users need accounts.
3. Otherwise restrict signup with `ALLOWED_EMAILS` or `ALLOWED_EMAIL_DOMAINS`.
4. Recreate the backend with `docker compose up -d backend`.

## Persistence and upgrades

Persistent state lives in the `multica_pgdata` and `multica_backend-uploads` volumes.
Their names are explicit in Compose, so moving this project directory does not create a new empty database.
Keep the top-level project name `multica` and these volume names when operating this deployment.
Use this directory for future Compose commands; the former root-level `multica/` directory is no longer the deployment path.

Back up both before upgrades, together with `.env` and any GitHub App private key.
The VCS encryption key is required to recover stored provider credentials.
Image upgrades may run forward-only database migrations; check release notes and keep a database dump before changing versions.
Never run `docker compose down -v` unless deleting the instance is intentional.

Upgrade by changing `MULTICA_IMAGE_TAG` to a reviewed release, then run:

```bash
docker compose pull backend frontend
docker compose up -d --wait
```

Keep backend and frontend on the same release. Database migrations are forward-only: restoring an older image alone is not a safe rollback after an upgrade; restore the pre-upgrade database and uploads together with the matching configuration if rollback is required.

The v0.6.0 self-host release introduces anonymous telemetry. This project defaults `DO_NOT_TRACK` to `true` to opt out. Optional Redis, managed Cloud, plugin surfaces, LLM helpers, and new chat integrations are left unconfigured; enable them only when needed, following upstream documentation.

Refer to the upstream Multica self-hosting and environment-variable documentation when changing application behavior.

## Public deployment security

- Keep `APP_ENV=production`, independent random credentials, and an empty `MULTICA_DEV_VERIFICATION_CODE`.
- Keep general signup closed; use explicit invitations or a narrow email allowlist when adding users.
- Keep PostgreSQL on the private project network. Application ports are not published to the host.
- Expose the web and API through HTTPS. The current two-origin layout matches the upstream reverse-proxy recipe; browser requests remain on the web origin, so `COOKIE_DOMAIN` stays empty.
- Preserve authenticated API and daemon WebSocket access through Cloudflare Tunnel. A browser-only access gate can prevent CLI, daemon, and webhook clients from connecting.
- Keep Cloudflare Tunnel origin TLS verification enabled. Review Cloudflare access and caching rules in the dashboard; do not cache authenticated API or auth responses.
- Leave `MULTICA_TRUSTED_PROXIES` empty unless trusted proxy addresses are deliberately configured; never trust every caller's forwarded headers.
- Keep `.env` and private key files at mode `600` and outside Git.
- The backend and frontend use health checks, no privilege escalation, and no Linux capabilities.
- Agent runs execute with the daemon user's permissions. Scope the daemon user's repositories and credentials deliberately; the server containers do not provide a sandbox for remote runs.

The pinned `v0.6.0` official web image contains Next.js `16.3.4`, verified from the published Linux amd64 image on 2026-10-01. It includes the patched version for the AVIF image-optimization advisory (fixed in `16.3.3`), but remains in the affected version range of the Node.js `ImageResponse` advisory (fixed in `16.3.6`). The latter affects Node.js `next/og` routes that pass attacker-controlled values into SVG content, attributes, or styles; applicability to this deployment has not been established. The operator accepted this remaining version-level risk when requesting the latest official release. Upgrade to an official image containing the relevant patch and verify its actual Next.js version before considering that advisory resolved; container hardening is not a substitute for the patch.

## References

- [Official self-host quickstart](https://multica.ai/docs/self-host-quickstart)
- [Environment variables](https://multica.ai/docs/environment-variables)
- [Sign-in and signup](https://multica.ai/docs/auth-setup)
- [Daemon security model](https://multica.ai/docs/security-model)
- [AVIF image-optimization advisory](https://github.com/vercel/next.js/security/advisories/GHSA-2xp9-vwfh-vxw4)
- [Node.js ImageResponse advisory](https://github.com/vercel/next.js/security/advisories/GHSA-vcvr-r3jv-pc5j)
