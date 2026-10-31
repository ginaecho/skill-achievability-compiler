# Observability APIs

Fetch the applicable reference for current signatures, field locations, units, authentication, and query syntax. Do not infer the Tail event schema from an OpenTelemetry span or a Logpush record.

| Task | Maintained documentation |
| --- | --- |
| Emit console messages and check supported methods | [Console API]([url-1]) |
| Filter, group, and aggregate stored Workers Logs | [Query Builder]([url-2]) |
| Query built-in Workers metrics with GraphQL | [Querying Workers metrics]([url-3]) |
| Define Analytics Engine fields and call `writeDataPoint()` | [Write data points]([url-4]) |
| Authenticate and query Analytics Engine datasets | [SQL API]([url-5]) |
| Calculate counts, sums, and averages on sampled events | [Analytics Engine sampling]([url-6]) |
| Implement a Tail consumer and inspect event properties | [Tail handler API]([url-7]) |
| Create and manage Logpush jobs | [Logpush API configuration]([url-8]) |
| Select exported Workers event fields | [Workers Trace Events dataset]([url-9]) |
| Export OTLP logs and traces | [OpenTelemetry export]([url-10]) |

Keep dataset field meanings and units consistent between writers and queries. Follow the SQL reference linked from the SQL API for supported date bucketing and aggregate functions; do not assume another SQL dialect's syntax works here. Account for sampling in averages as well as counts and sums.

See [configuration.md](configuration.md) for setup and [patterns.md](patterns.md) for application-level decisions.
