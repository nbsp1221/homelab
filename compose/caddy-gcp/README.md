# GCP HTTPS entrypoint

This project serves `https://beszel.retn0.dev` on `retn0-srv-gcp-01` over Tailscale. Caddy proxies requests to the separate `beszel-hub` stack and returns `gcp-caddy-ok` at `/healthz` for checking the proxy itself.

## Configuration and state

`hosts/retn0-srv-gcp-01/host.yaml` declares the domain and Tailscale IPv4/IPv6 listeners. Only TCP 443 is published, bound to those addresses. Caddy handles certificates automatically through Cloudflare DNS-01. The host-local `/opt/stacks/caddy-gcp/.env` contains `CLOUDFLARE_API_TOKEN` with Zone:Read and DNS:Edit permissions for the relevant zone. Keep credentials outside Git.

The project uses the [Cloudflare module maintainers' prebuilt image](https://github.com/caddy-dns/cloudflare/pkgs/container/cloudflare), `ghcr.io/caddy-dns/cloudflare:v0.2.4`, pinned by digest. This image contains Caddy `2.11.2`; the tag refers to the Cloudflare module version. Deployments pull the image without compiling Caddy.

Named volumes preserve certificate and ACME state under `/data` and Caddy runtime state under `/config`. The project creates `caddy-network`, which the Hub also joins. Hub port 8090 is reachable over this Docker network without being published on the host. The proxy configuration follows [Beszel's Caddy guidance](https://beszel.dev/guide/reverse-proxy), including WebSocket support and the upstream timeout.

## Deploy from the controller

Run from `deploy/pyinfra`. For initial provisioning, an operator-provided private environment file can seed an absent remote `.env` using `--data stack_env_file=/absolute/path/to/private.env`. Existing remote environment files are preserved. Subsequent deployments use the host-local credential file:

```bash
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --data stack=caddy-gcp --dry --serial
uv run pyinfra inventories/production.py deploys/stacks.py \
  --limit retn0-srv-gcp-01 --data stack=caddy-gcp --serial --yes
```

Deploy `caddy-gcp` before [`beszel-hub`](../beszel-hub/README.md) so their shared Docker network exists. The executor explicitly uploads only `compose.yaml` and `config/Caddyfile`, validates the staged Compose and Caddy configurations, promotes the public configuration files, and applies the Compose project while preserving its volumes. It then runs [Caddy's standard reload command](https://caddyserver.com/docs/running#docker-compose) to apply the Caddyfile. Identical configurations do not force a reload or container recreation; Compose still recreates the container when its service definition or image changes. The existing Beszel agent is excluded by the stack selector.

The reload operation uses pyinfra's built-in retries, with up to three retries two seconds apart, because Compose may return before a newly started container's admin API is ready.

## Verify

From a Tailscale-connected client, check both address families with certificate validation enabled:

```bash
curl --noproxy '*' -4 --fail https://beszel.retn0.dev/api/health
curl --noproxy '*' -6 --fail https://beszel.retn0.dev/api/health
curl --noproxy '*' --fail https://beszel.retn0.dev/healthz
```

The Hub health endpoint must return HTTP 200, and `/healthz` must return `gcp-caddy-ok`. Open the root URL to reach the Beszel UI. This Hub uses a separate database and receives metrics from the main-host, GCP, and both OCI agents, each registered with its own token. The old main-host Hub and its data have been removed; the separate desktop will be registered later.

## Local checks

```bash
docker compose --env-file .env.example config --quiet
pnpm lint:compose
```
