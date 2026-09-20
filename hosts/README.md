# Host-to-project map

This is the small deployment map for the four hosts. `pyinfra/` owns the cloud OS and Docker baseline; each Compose project owns one application stack. Runtime data, populated `.env` files, and Hub UI state stay outside Git.

| Host | Beszel role | Compose project | State |
| --- | --- | --- | --- |
| `retn0-srv-main` | Hub and local NVIDIA agent | [`beszel/`](../beszel/README.md) | Existing deployment; add tailnet-only Hub access for cloud agents |
| `retn0-srv-gcp-01` | Generic cloud agent | [`compose/beszel-agent/`](../compose/beszel-agent/README.md) | First adoption target; preserve existing agent identity/data |
| `retn0-srv-oci-01` | None yet | — | Consider after GCP verification |
| `retn0-srv-oci-02` | None yet | — | Consider after GCP verification |

Do not infer that a row marked as a target is already deployed. Keep project-specific overrides only when a host actually needs them; do not add empty per-host directories.
