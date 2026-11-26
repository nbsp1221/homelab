# Hosts

Each `hosts/<hostname>/host.yaml` records a server's provider and the Compose stacks that this repository's deployment executor should apply there. This directory describes placement and host-specific non-secret values; it does not contain application Compose definitions or deployment commands.

For example, `hosts/cloud-example-01/host.yaml` can assign a bootstrap stack to a cloud host.

```yaml
provider: gcp
stacks:
  arcane-agent:
    bootstrap: true
```

An empty `stacks: {}` means pyinfra has no Compose stacks assigned to that host.

The same files supply the cloud pyinfra inventory. `provider` selects the GCP or OCI connection defaults in [`deploy/pyinfra/group_data/`](../deploy/pyinfra/group_data/).

`bootstrap: true` places the project in the target operator's home and requires selecting it by name. [Arcane Agent](../stacks/arcane-agent/README.md) uses this so it can connect to the Manager before Arcane manages workloads on the host.

Only put non-secret values in `host.yaml`. Keep populated `.env` files and persistent data on the target host, outside Git. Removing a stack from `host.yaml` does not stop or delete it; decommissioning is a separate, deliberate operation.
