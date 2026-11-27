# GCP HTTPS entrypoint

This stack provides an HTTPS reverse proxy for [Beszel Hub](../../stacks/beszel-hub/README.md) over Tailscale. Caddy returns `gcp-caddy-ok` at `/healthz` so the proxy can be checked independently of the Hub.

## Configuration and state

The controller's private `gcp_ingress.py` group data supplies `CADDY_DOMAIN` and the host's Tailscale IPv4 and IPv6 addresses through `CADDY_BIND_IPV4` and `CADDY_BIND_IPV6`. Only TCP 443 is published, bound to those addresses. Caddy obtains certificates via Cloudflare DNS-01. Set `CLOUDFLARE_API_TOKEN` in the deployed stack's local `.env` with Zone:Read and DNS:Edit permissions for the relevant zone. Keep the token outside Git.

The project uses the [Cloudflare module maintainers' prebuilt image](https://github.com/caddy-dns/cloudflare/pkgs/container/cloudflare), `ghcr.io/caddy-dns/cloudflare:v0.2.4`, pinned by digest. This image contains Caddy `2.11.2`; the tag refers to the Cloudflare module version. Deployments pull the image without compiling Caddy.

Named volumes preserve certificate and ACME state under `/data` and Caddy runtime state under `/config`. The project creates `caddy-network`, which the Hub also joins. Hub port 8090 is reachable over this Docker network without being published on the host. The proxy configuration follows [Beszel's Caddy guidance](https://beszel.dev/guide/reverse-proxy), including WebSocket support and the upstream timeout.

## Deploy from the controller

Run from `pyinfra`. For initial provisioning, an operator-provided private environment file can seed an absent remote `.env` using `--data stack_env_file=/absolute/path/to/private.env`. Existing remote environment files are preserved. Subsequent deployments use the host-local credential file.

Preview and apply the Caddy stack. Replace `gcp-01` with your host's inventory name.

```bash
uv run pyinfra --group-data "$HOME/.config/homelab/group_data" inventories/cloud.py tasks.stacks.apply \
  --limit gcp-01 --data stack=caddy-gcp --dry --serial
uv run pyinfra --group-data "$HOME/.config/homelab/group_data" inventories/cloud.py tasks.stacks.apply \
  --limit gcp-01 --data stack=caddy-gcp --serial --yes
```

Deploy `caddy-gcp` before [`beszel-hub`](../../stacks/beszel-hub/README.md) so their shared Docker network exists. The executor validates the staged Compose and Caddy files, applies the project while preserving its volumes, then runs [Caddy's standard reload command](https://caddyserver.com/docs/running#docker-compose).

## Verify

From a Tailscale-connected client, check both address families with certificate validation enabled. Replace `beszel.example.com` with your domain.

```bash
curl --noproxy '*' -4 --fail https://beszel.example.com/api/health
curl --noproxy '*' -6 --fail https://beszel.example.com/api/health
curl --noproxy '*' --fail https://beszel.example.com/healthz
```

The Hub health endpoint must return HTTP 200, and `/healthz` must return `gcp-caddy-ok`. Open the root URL to reach the Beszel UI.

## Local checks

```bash
docker compose --env-file .env.example config --quiet
pnpm lint:compose
```
