# Repository instructions

## Testing

- Test an observable contract through the normal entry point. Assert results or required effects at boundaries such as Docker, the filesystem, and network protocols. Replace external dependencies when needed for isolation.
- Keep tests that catch a concrete regression and remove redundant checks. Avoid assertions about configuration literals, internal call order, or source layout unless they are part of the contract. Preserve meaningful coverage when replacing a brittle test.
- Use synthetic fixtures for hostnames, network addresses, user identities, paths, and credentials. Keep production inventory, actual host data, and personal or sensitive values out of test fixtures and expectations.
- Run the affected checks listed in the [README](README.md#testing).

## Documentation

- Use the README to explain what the project does and how to set it up and verify it. Link to detailed guides and keep agent-specific instructions in `AGENTS.md`.
- Document required settings and shared defaults with synthetic examples. Keep credentials, personal data, real hostnames and addresses, host-specific paths, and one-off operational records out of public docs.
- Update the affected docs when setup or user-facing behavior changes. Check that commands and examples match the current configuration and that links resolve.
