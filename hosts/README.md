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
| `retn0-srv-gcp-01` | `beszel-agent`, `caddy-gcp`, `beszel-hub`, `komodo-periphery` (explicit) |
| `retn0-srv-oci-01` | `beszel-agent`, `komodo-periphery` (explicit) |
| `retn0-srv-oci-02` | `beszel-agent`, `komodo-periphery` (explicit) |

The cloud hosts also supply the pyinfra inventory through these same files. `provider` selects the existing GCP or OCI connection defaults in `deploy/pyinfra/group_data/`. The main host is local and is not part of the cloud pyinfra inventory.

`bootstrap: true` places a stack under `~/compose/` on the target and requires selecting it by name. [Komodo Periphery](../compose/komodo-periphery/README.md) uses this so that it can start before Komodo manages deployments on that host.

The [GCP Hub](../compose/beszel-hub/README.md) is served at `https://beszel.retn0.dev`. It receives metrics from the [main host's NVIDIA agent](../compose/beszel-agent-nvidia/README.md) and the [GCP and OCI agents](../compose/beszel-agent/README.md). Each system has its own token.

Only put non-secret values in `host.yaml`. Keep populated `.env` files and persistent data on the target host, outside Git. Removing a stack from `host.yaml` does not stop or delete it; decommissioning is a separate, deliberate operation.
