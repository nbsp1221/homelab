# Hosts

Each `hosts/<hostname>/host.yaml` records a server's provider and the Compose stacks that this repository's deployment executor should apply there. This directory describes placement and host-specific non-secret values; it does not contain application Compose definitions or deployment commands.

```yaml
provider: gcp
stacks:
  beszel-agent:
    env:
      BESZEL_HUB_URL: https://beszel.retn0.dev
```

An empty `stacks: {}` means this repository has not adopted any Compose stacks for automated deployment on that host. It does not mean the server is empty or that existing services should be removed. In particular, the main host's NVIDIA Beszel agent remains managed in its current directory.

| Host | Stack placement currently managed here |
| --- | --- |
| `retn0-srv-main` | None yet; existing services remain in their current locations |
| `retn0-srv-gcp-01` | `beszel-agent`, `caddy-gcp`, and `beszel-hub` |
| `retn0-srv-oci-01` | `beszel-agent`; applied and verified |
| `retn0-srv-oci-02` | `beszel-agent`; applied and verified |

The cloud hosts also supply the pyinfra inventory through these same files. `provider` selects the existing GCP or OCI connection defaults in `deploy/pyinfra/group_data/`. The main host is local and is not part of the cloud pyinfra inventory.

The optional `docker` host policy controls the [Docker startup dependency](../deploy/pyinfra/README.md#docker-startup-on-the-gcp-monitoring-host), independently of stack names or placement. `wait_for_tailscale: true` makes Docker wait for `tailscale_bind_addresses`. Omitting `docker` leaves existing configuration unmanaged; only an explicit `wait_for_tailscale: false` disables this executor's drop-in. Removing a stack assignment never removes the host policy.

The GCP definition declares each listener address once in that policy and shares it with the Caddy environment through standard YAML anchors and aliases. Change the anchor value when changing an address. Apply the host startup policy before deploying stacks; the stack executor checks both the file and the loaded systemd configuration before writing application files.

The GCP Hub is served at `https://beszel.retn0.dev`. The main-host, GCP, and both OCI agents report there, each using its own system-specific token. The main-host NVIDIA agent remains managed in the existing `beszel/` project using its host-local `BESZEL_HUB_URL`; it is not part of the cloud inventory. The old Hub and its historical data have been removed. The separate desktop will be registered later.

Only put non-secret values in `host.yaml`. Keep populated `.env` files and persistent data on the target host, outside Git. Removing a stack from `host.yaml` does not stop or delete it; decommissioning is a separate, deliberate operation.
