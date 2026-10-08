# Hosts

Each `hosts/<hostname>/host.yaml` records a server's provider and the Compose stacks that this repository's deployment executor should apply there. This directory describes placement and host-specific non-secret values; it does not contain application Compose definitions or deployment commands.

```yaml
provider: gcp
stacks:
  beszel-agent:
    env:
      BESZEL_HUB_URL: https://beszel-legacy.retn0.dev
```

An empty `stacks: {}` means this repository has not adopted any Compose stacks for automated deployment on that host. It does not mean the server is empty or that existing services should be removed. In particular, the main host's existing Beszel Hub remains managed in its current directory.

| Host | Stack placement currently managed here |
| --- | --- |
| `retn0-srv-main` | None yet; existing services remain in their current locations |
| `retn0-srv-gcp-01` | `beszel-agent`, `caddy-gcp`, and `beszel-hub` |
| `retn0-srv-oci-01` | `beszel-agent`; applied and verified |
| `retn0-srv-oci-02` | `beszel-agent`; applied and verified |

The cloud hosts also supply the pyinfra inventory through these same files. `provider` selects the existing GCP or OCI connection defaults in `deploy/pyinfra/group_data/`. The main host is local and is not part of the cloud pyinfra inventory.

The GCP Hub is served at `https://beszel.retn0.dev`. Cloud agents currently report to the existing main-host Hub at `https://beszel-legacy.retn0.dev` with their existing credentials. Switching them to the GCP Hub requires separate registration and credential updates.

Only put non-secret values in `host.yaml`. Keep populated `.env` files and persistent data on the target host, outside Git. Removing a stack from `host.yaml` does not stop or delete it; decommissioning is a separate, deliberate operation.
