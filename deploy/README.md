# Deployment executors

`compose/` owns application stacks. `hosts/` owns placement and host-specific values. This directory contains only the code that applies those definitions to a server.

`pyinfra/` currently manages the GCP and OCI operating-system baseline and is the first executor for Compose stack deployment. Deployment is manual: a Git push alone does not change any server. See [`pyinfra/README.md`](pyinfra/README.md) for validation and commands.

An executor may be replaced without rewriting the Compose stacks or host definitions. It must preserve host-local secrets and data, validate the resolved Compose configuration, and never infer that removing a stack assignment authorizes deletion.
