# GCP HTTPS entrypoint

This stack provides an HTTPS reverse proxy for [Beszel Hub](../../stacks/beszel-hub/README.md) over Tailscale. Caddy returns `gcp-caddy-ok` at `/healthz` so the proxy can be checked independently of the Hub.

## Configuration and state

Set `CADDY_DOMAIN` and the host's Tailscale IPv4 and IPv6 addresses in the deployment directory's private `.env` using `CADDY_BIND_IPV4` and `CADDY_BIND_IPV6`. Only TCP 443 is published, bound to those addresses. Caddy obtains certificates via Cloudflare DNS-01. Set `CLOUDFLARE_API_TOKEN` in the deployed stack's local `.env` with Zone:Read and DNS:Edit permissions for the relevant zone. Keep the token outside Git.

The project uses the [Cloudflare module maintainers' prebuilt image](https://github.com/caddy-dns/cloudflare/pkgs/container/cloudflare), `ghcr.io/caddy-dns/cloudflare:v0.2.4`, pinned by digest. This image contains Caddy `2.11.2`; the tag refers to the Cloudflare module version. Deployments pull the image without compiling Caddy.

Named volumes preserve certificate and ACME state under `/data` and Caddy runtime state under `/config`. The project creates `caddy-network`, which the Hub also joins. Hub port 8090 is reachable over this Docker network without being published on the host. The proxy configuration follows [Beszel's Caddy guidance](https://beszel.dev/guide/reverse-proxy), including WebSocket support and the upstream timeout.

## Install and recover

On the GCP host, copy `compose.yaml`, `.env.example` and `config/Caddyfile` into the stack's deployment directory. For an existing stack, reuse its deployment directory and original Compose project name. For a fresh deployment, use a directory owned by the Docker-enabled operator, such as `~/compose/caddy-gcp/`, and set its mode to `0700`. Create `.env` from the example on first install and set its mode to `0600`. Preserve the existing `.env` when applying updates, including any values previously supplied through pyinfra.

Run these commands from the deployment directory for installs and updates. Start Caddy before [Beszel Hub](../../stacks/beszel-hub/README.md) so their shared Docker network exists. The last command loads the validated Caddyfile even when Compose keeps the existing container.

```sh
docker compose config --quiet &&
  docker compose run --rm --no-deps caddy caddy validate --config /etc/caddy/Caddyfile &&
  docker compose up -d --wait --wait-timeout 120 &&
  docker compose exec -T caddy caddy reload --config /etc/caddy/Caddyfile
```

For recovery, inspect `docker compose ps --all` and `docker compose logs caddy`. Restore the previous configuration files if needed and reapply from the same directory with the original project name, private `.env`, and named volumes.

## Verify

From a Tailscale-connected client, check both address families with certificate validation enabled. Replace `beszel.example.com` with your domain.

```bash
curl --noproxy '*' -4 --fail https://beszel.example.com/api/health
curl --noproxy '*' -6 --fail https://beszel.example.com/api/health
curl --noproxy '*' --fail https://beszel.example.com/healthz
```

To check the configured listeners directly, use the domain and both listener addresses from the host's `.env`. The example addresses below are placeholders. `--resolve` sends each request to the specified address while keeping the hostname for TLS certificate verification.

```bash
domain=beszel.example.com
ipv4=192.0.2.10
ipv6=2001:db8::10

probe() {
  response=$(curl --noproxy '*' --silent --show-error --write-out '\n%{http_code}' \
    --resolve "$domain:443:$1" "https://$domain$2") || return 1
  printf '%s %s\n%s\n' "$1" "$2" "$response"
  [[ ${response##*$'\n'} == 200 ]]
}

probe "$ipv4" /healthz &&
  probe "$ipv4" /api/health &&
  probe "[$ipv6]" /healthz &&
  probe "[$ipv6]" /api/health
```

The Hub health endpoint must return HTTP 200, and `/healthz` must return `gcp-caddy-ok`. Open the root URL to reach the Beszel UI.

## Local checks

```bash
docker compose --env-file .env.example config --quiet
pnpm lint:compose
```
