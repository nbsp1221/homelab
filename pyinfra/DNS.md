# GCP DNS integration

The GCP host explicitly opts into `manage_resolved_dns` in `group_data/gcp.py`. Other hosts default to unmanaged DNS, so this deploy does not rewrite the working OCI resolver configuration. Tailscale installation and enrollment remain separate prerequisites.

The policy uses `/etc/resolv.conf -> /run/systemd/resolve/stub-resolv.conf`, with Tailscale registering its DNS server on the `tailscale0` link through systemd-resolved. The Google-provided DNS configuration, metadata resolver, internal search domains, Tailscale identity, host secrets and application volumes are preserved.

## Why this is managed

The GCP host's former `/run/systemd/resolve/resolv.conf` link exposed upstream DNS directly. Tailscale therefore selected its direct file manager while systemd-resolved was also running. Repeated DNS configuration during boot restarted resolved enough to hit systemd's start limit. Ordinary applications still used Tailscale DNS, while applications querying resolved directly could not resolve Tailscale names.

Simply starting resolved or clearing its failure state leaves these two resolver paths inconsistent. The deploy checks the canonical stub link, both services' active/enabled states, and Tailscale's registered link DNS. It does not activate resolved while inspecting an unhealthy host: the D-Bus read uses `--auto-start=no`.

## Prerequisites and independent access

The migration briefly stops Tailscale. **Run it through an independent GCP IAP SSH connection, after operator approval.** An ordinary Tailscale SSH connection is rejected before any changes when migration is needed. A converged host is a no-op and does not need this transport override.

Configure the IAP alias and Google credentials on the controller. Add the independently verified host key to the alias's `UserKnownHostsFile` under its configured `HostName`. Paramiko checks the effective hostname. An OpenSSH `HostKeyAlias` entry alone does not supply that mapping. Include the original cloud, public, and private DNS probes in the controller's private `gcp.py` group data.

The target must already have enabled Tailscale and systemd-resolved services, the resolver files, `busctl`, `getent`, `resolvectl`, `timeout`, and `tailscale wait`. Install packages and enroll the node before running this procedure.

## Preview and apply

From `pyinfra`, replace both aliases with the controller's configured names.

```bash
uv run pyinfra --group-data "$HOME/.config/homelab/group_data" inventories/cloud.py tasks.dns.configure_dns \
  --limit gcp-01 \
  --data ssh_hostname=gcp-01-iap --dry --serial
```

After checking the target, the preview, IAP access and the maintenance impact, apply the same command with `--serial --yes` in place of `--dry --serial`. Expect a temporary loss of Tailscale connectivity and monitoring while its daemon restarts. IAP remains the management path. No reboot is performed.

The migration runs stop/link/start in one remote operation. It keeps private copies of the prior resolver file and any Tailscale resolver backup in a unique `/var/backups/homelab-dns.*` directory before stopping Tailscale. It starts resolved, promotes the stub symlink and starts the existing Tailscale daemon. It then waits for Tailscale and verifies the three declared public, GCP and tailnet probe names through both the ordinary resolver and resolved's native API.

An error or handled termination signal triggers an attempt to restore both previous DNS files and start Tailscale again; the operation still fails so the operator can inspect the result. A power loss, `SIGKILL`, filesystem failure or failed recovery command cannot be guaranteed recoverable by a shell trap. Keep IAP available and check the retained backup path in the output before declaring recovery complete. No automatic backup deletion is performed.

## Verify and check convergence

Run the independent read-only DNS check.

```bash
uv run pyinfra --group-data "$HOME/.config/homelab/group_data" inventories/cloud.py tasks.dns.verify_dns \
  --limit gcp-01 --serial --yes
```

DNS verification requires the stub link, both enabled/running services and Tailscale link DNS. It queries every declared probe through `getent` and `resolvectl query --cache=no`, with bounded query timeouts. Check the HTTPS endpoints separately using the [Caddy operating procedure](../compose/caddy-gcp/README.md#verify).

Run `tasks.dns.configure_dns` again after a successful apply; it should plan zero operations and avoid another Tailscale restart. The baseline leaves DNS migration to this dedicated IAP procedure.

During an approved later reboot, confirm resolved/Tailscale remain healthy, the daemon selects `systemd-resolved` DNS mode, all three probe categories still resolve, and the dual-stack monitoring checks succeed. A current runtime check does not establish persistence through reboot.

## Manual recovery

If automatic restoration fails, use the verified IAP path. Inspect the reported private backup directory, the resolver link, Tailscale state and service journals first. During an approved recovery, stop Tailscale, restore the saved `resolv.conf` with its original file/link type and restore the saved Tailscale backup if present, then start Tailscale and test DNS and the Hub again. Preserve existing enrollment state and application volumes; do not use `tailscale logout`, create a new Beszel identity, or delete volumes to fix resolver configuration.
