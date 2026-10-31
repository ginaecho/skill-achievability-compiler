# Hyperdrive troubleshooting

Start with the actual error and the affected configuration. Fetch [Troubleshoot and debug]([url-1]) for current error codes and diagnosis rather than guessing from a generic connection failure.

| Symptom | What to inspect and where to read |
|---------|----------------------------------|
| Connection refused or authentication failure | Check origin reachability and credentials using [troubleshooting]([url-1]) and [firewall/networking configuration]([url-2]). |
| Private database or TLS failure | Follow the selected [Workers VPC]([url-3]) or [Tunnel/Access]([url-4]) path and its certificate prerequisites; see [SSL/TLS configuration]([url-5]). |
| Pool exhaustion or too many connections | Distinguish client connection lifetime from origin pool capacity. Read [connection lifecycle]([url-6]), [pool tuning]([url-7]), and [limits]([url-8]). |
| Query timeout | Check the current [limits]([url-8]) and [metrics]([url-9]) before changing query or transaction design. |
| Stale reads or unexpectedly uncached queries | Inspect the binding's cache configuration and query eligibility in [query caching]([url-10]). Writes do not purge cached reads; do not treat prepared-statement settings as cache controls. |
| Slow multi-query requests | Inspect [metrics]([url-9]) and check whether Worker placement matches the regional database. Follow [placement setup](./configuration.md#place-compute-near-the-database); a Hyperdrive binding alone does not place compute near the origin. |
| Local connection failure, ignored environment variable, or absent cache behavior | Check binding names, local connection overrides, precedence, and remote testing in [local development]([url-11]). |
| Unsupported driver or SQL feature | Check [supported databases and features]([url-12]) and the selected [driver guide](./api.md). |

## Capacity and changes

Retrieve [limits]([url-8]) and [pricing]([url-13]) for current plan allowances, connection and query bounds, and limit-increase guidance. Check [release notes]([url-14]) when behavior changes after an upgrade.

See [configuration.md](./configuration.md) to change a configuration and [patterns.md](./patterns.md) to revisit freshness or connection decisions.
