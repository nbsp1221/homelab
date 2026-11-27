# Arcane Git Pull syncs

Store one JSON file per Arcane environment. The file maps projects to their branch and Compose path in this repository. Compose definitions live in [stacks/](../../stacks/), and Arcane handles application updates.

Use [example.json](example.json) as a template and replace its sample stack path and Arcane repository name. Register the repository with read-only access, then select the target Agent in [Arcane's import dialog](https://getarcane.app/docs/docker/git-sync#import-multiple-syncs-from-json). Import can run the first pull even when automatic sync is off. Follow the [adoption procedure](../../stacks/arcane/README.md#adopt-an-existing-stack) for an existing project.

For a stack with a local build context or other repository-relative files, set `"syncDirectory": true` in its sync entry. For example, [Bifrost](../../stacks/bifrost/) needs its Dockerfile and patches copied with the Compose file.

Keep credentials and service environment files outside Git. Bootstrap or recover [Arcane Manager](../../stacks/arcane/README.md#bootstrap-with-pyinfra) and [Arcane Agent](../../stacks/arcane-agent/README.md#bootstrap-with-pyinfra) through pyinfra.
