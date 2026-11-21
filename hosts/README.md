# Hosts

Each `hosts/<hostname>/host.yaml` records a server's provider and the Compose stacks that this repository's deployment executor should apply there. This directory describes placement and host-specific non-secret values; it does not contain application Compose definitions or deployment commands.

```yaml
provider: gcp
stacks:
  beszel-hub:
    env:
      BESZEL_APP_URL: https://beszel.retn0.dev
```

An empty `stacks: {}` means pyinfra has no Compose stacks assigned to that host.

| Host | Stack placement currently managed here |
| --- | --- |
| `retn0-srv-main` | None |
| `retn0-srv-gcp-01` | `caddy-gcp`, `beszel-hub`, `komodo-periphery` (explicit) |
| `retn0-srv-oci-01` | `komodo-periphery` (explicit) |
| `retn0-srv-oci-02` | `komodo-periphery` (explicit) |

The cloud hosts also supply the pyinfra inventory through these same files. `provider` selects the existing GCP or OCI connection defaults in `deploy/pyinfra/group_data/`. The main host is local and is not part of the cloud pyinfra inventory.

`bootstrap: true` places a stack under `~/compose/` on the target and requires selecting it by name. [Komodo Periphery](../compose/komodo-periphery/README.md) uses this so that it can start before Komodo manages deployments on that host.

In Komodo, deploy the [NVIDIA agent](../compose/beszel-agent-nvidia/README.md) on the main host and the [standard agent](../compose/beszel-agent/README.md) on GCP and OCI. Each system uses its own token to connect to the [GCP Hub](../compose/beszel-hub/README.md).

Only put non-secret values in `host.yaml`. Keep populated `.env` files and persistent data on the target host, outside Git. Removing a stack from `host.yaml` does not stop or delete it; decommissioning is a separate, deliberate operation.
