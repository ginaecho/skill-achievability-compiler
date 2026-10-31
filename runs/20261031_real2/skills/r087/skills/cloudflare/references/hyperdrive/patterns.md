# Hyperdrive design patterns

See [api.md](./api.md) for maintained driver and ORM examples. Use the following decisions to select a pattern, then fetch its linked documentation for implementation.

| Workload or decision | Guidance and documentation |
|----------------------|----------------------------|
| Popular content or analytics dashboards | Cache only when the product can tolerate the configured stale window. Use [query caching]([url-1]) for eligibility, parameters, and settings. |
| Mixed cached reads and fresh reads | Route authentication, permissions, and reads after writes through a cache-disabled configuration. Writes do not invalidate cached results; see [read-after-write behavior]([url-2]). |
| Multi-tenant queries | Derive tenant scope from authenticated application context and apply it to every query. A cache is not an authorization boundary. Review [query caching]([url-1]) for the selected query's behavior. |
| Globally distributed callers | Understand the distinction between fast connection setup and the remaining query round trip in [how Hyperdrive works]([url-3]). |
| Multiple sequential database queries | For one regional database, configure an explicit region hint using [placement setup](./configuration.md#place-compute-near-the-database). Compare deployed request duration and [Hyperdrive metrics]([url-4]) with representative cache behavior. |
| Transactions or connection-local state | Keep transactions short and do not assume state survives across transactions. Fetch [connection pooling]([url-5]) and [supported features]([url-6]) before relying on session settings. |
| Client lifetime and pool sizing | Create clients per handler invocation; Hyperdrive owns the origin pool. Use [connection lifecycle]([url-7]) and [pool tuning]([url-8]) instead of a global driver pool or copied connection counts. |

Separate application correctness from acceleration: use parameterized queries, enforce tenant access in the application, and select freshness before tuning cache hit rate. See [gotchas.md](./gotchas.md) when observed behavior differs from the design.
