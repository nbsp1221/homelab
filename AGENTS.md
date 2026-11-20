# Repository instructions

## Testing

- Test an observable contract through the normal entry point. Assert results or required effects at boundaries such as Docker, the filesystem, and network protocols. Replace external dependencies when needed for isolation.
- Keep tests that catch a concrete regression. Remove redundant assertions that mirror configuration literals, internal call sequences, or source layout. Preserve meaningful coverage when replacing a brittle test.
- Use synthetic fixtures for hostnames, network addresses, user identities, paths, and credentials. Keep production inventory, actual host data, and personal or sensitive values out of test fixtures and expectations.
- Run the affected checks listed in the [README](README.md#testing).
