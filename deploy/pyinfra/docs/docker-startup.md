# Docker startup and Tailscale address readiness

## Problem and ownership

Docker reserves a published host address before starting the container process. On the GCP monitoring host, both Caddy listeners require Tailscale addresses. A successful `tailscaled.service` start is not proof that those addresses can be bound, and Docker container restart policies do not provide this host prerequisite.

The initial implementation inferred a host-wide dependency from the application name `caddy-gcp`. That mixed application placement with host lifecycle: removing an assignment could remove a prerequisite of a still-running application, and the application deploy could change listener addresses without updating the prerequisite. A file-change notification also could not recover a deployment interrupted between saving the file and reloading systemd.

These are local configuration ownership and reconciliation problems. The host policy and deployment preflight below are repository design decisions, not features prescribed by Tailscale.

## Declarative host contract

```yaml
provider: gcp
docker:
  wait_for_tailscale: true
  tailscale_bind_addresses:
    - &tailscale_ipv4 100.64.0.10
    - &tailscale_ipv6 fd7a:115c:a1e0::10
stacks:
  example-proxy:
    env:
      LISTEN_IPV4: *tailscale_ipv4
      LISTEN_IPV6: *tailscale_ipv6
```

The executor accepts specific unscoped unicast IPv4/IPv6 addresses and has no application-name, provider-name or interface-name dependency. [YAML anchors and aliases](https://yaml.org/spec/1.2.2/#3222-anchors-and-aliases) share the values without introducing a custom reference language. The deployed Compose projects still receive ordinary environment strings. The explicit enable/disable flag is separate from address data, so disabling the prerequisite does not break application aliases.

The three policy states are intentional:

| Host definition | Executor behavior |
| --- | --- |
| No `docker` key | Unmanaged; preserve any existing drop-in |
| `wait_for_tailscale: true` and a nonempty address list | Converge the managed prerequisite to these addresses |
| Explicit `wait_for_tailscale: false` | Remove only this executor's drop-in and reload systemd as needed; retain address data |

Removing or renaming a stack never changes this host contract. Disabling it requires an explicit configuration change and the usual approval before production application. Other systemd drop-ins, application definitions and persistent data are preserved.

## Startup and deployment behavior

The Docker service gets additive pre-start commands: the official `tailscale wait --timeout=60s`, then exact host address checks excluding tentative and DAD-failed addresses. The checks search host interfaces by address rather than assuming `tailscale0`. They run before `dockerd` restores containers, including socket activation. They do not alter published ports, firewall rules or certificate handling.

On a failed pre-start command, Docker's service retries after 10 seconds with start-rate limiting disabled. There is no overall retry deadline. All Docker containers on the host wait until the prerequisite succeeds. This is a startup check, not continuous network supervision; it proves neither peer reachability nor application health. Container restoration stays with Docker's existing restart policies.

The baseline configures the prerequisite before Docker package management. The dedicated `deploys/docker_startup.py` changes only the managed file and reloads systemd when necessary, without starting or restarting services. It compares effective loaded paths, pre-start commands, ordering and retry settings as well as file changes. A saved file with an old or missing loaded policy therefore triggers reconciliation on the next apply, even if `NeedDaemonReload=no`.

Application deployment remains separate from machine configuration. Before any application writes, `deploys/stacks.py` checks that the declared host policy matches both its file and the loaded unit. A stale or missing prerequisite stops even a dry run and tells the operator to apply the dedicated host configuration first. `deploys/verify_docker_startup.py` performs the same read-only check; the normal baseline verification includes it too. Hosts without a declared policy bypass this check.

Change a shared address at its YAML anchor, apply the host prerequisite, verify it, then deploy the application. A separately approved Docker restart or reboot is still needed to verify production boot behavior. Omitting a policy leaves its last applied configuration in place and transfers its maintenance to the operator; it does not disable it.

## Upstream evidence and alternatives

- [Tailscale's readiness issue #11504](https://github.com/tailscale/tailscale/issues/11504) and the earlier [community discussion #3340](https://github.com/tailscale/tailscale/issues/3340) document the gap between daemon startup and a bindable address, including Caddy failures. Older sleep-based workarounds do not establish readiness. The current [official CLI](https://tailscale.com/docs/reference/tailscale-cli#wait) provides the explicit readiness primitive.
- [Tailscale 1.102.3 source](https://github.com/tailscale/tailscale/blob/v1.102.3/cmd/tailscale/cli/wait.go) checks the first assigned IP on an interface. Additional checks are necessary for this host's complete listener list. Its official `tailscale-online.target` is another integration option; a direct Docker pre-start gate keeps a failed check within Docker's service restart behavior and checks every activation.
- [systemd's network synchronization guidance](https://systemd.io/NETWORK_ONLINE/) explains that generic network targets are not a definition of this application's readiness. Merely adding `After=tailscaled.service` or `network-online.target` does not express the required addresses.
- [systemd service semantics](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html) specify that pre-start failure prevents the main command and that restart policy covers pre-start processes. [systemctl's documentation](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html#daemon-reload) distinguishes saved unit files from manager configuration.
- [systemd issue #31752](https://github.com/systemd/systemd/issues/31752) reports `NeedDaemonReload=no` after initially adding a drop-in directory on systemd 252.6. It motivates comparing loaded paths and commands instead of using that property alone. [Ansible's failure documentation](https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_error_handling.html#handlers-and-failure) independently describes how file changes and missed handlers can leave configuration unapplied. This executor reconciles state on the next invocation rather than relying only on change notifications.
- [Docker's recommendation](https://docs.docker.com/engine/containers/start-containers-automatically/) is to retain container restart policies rather than combine them with another container process manager. A separate Compose systemd supervisor would add a second lifecycle owner, and waiting inside a container happens after Docker has already attempted the host bind.
- [Moby issue #53928](https://github.com/moby/moby/issues/53928) additionally reports lost network attachment after a failed bind in Docker 29. This is community-reported behavior, not a reproduced defect on this production host. It supports preventing the initial bind failure rather than assuming a later container start repairs every case.

## Verification boundaries

Regression tests cover policy validation, stack renaming and unassignment, explicit disable versus unmanaged state, preserving application aliases when disabling, changing the shared YAML source, every required address, loaded-state drift, interrupted reload recovery and rejection before application writes. Generated units and failure/recovery behavior must also be checked against actual systemd; mocked operation plans alone cannot establish service behavior.

Production checks are read-only until separately approved. A passing source test, unit parser check or cloud dry run does not establish that the prerequisite has been applied or that a real reboot has exercised it.
