# Cloudflare Observability

Use this reference to choose a telemetry signal and find the maintained implementation guide. Fetch the linked documentation before writing configuration, queries, or export code; it is the source of truth for APIs, availability, retention, limits, and pricing.

## Choose a signal

| Need | Start here |
| --- | --- |
| Store, search, and investigate historical Worker logs | [Workers Logs]([url-1]) |
| Watch a deployment or reproduce an issue live | [Real-time logs and Wrangler tail]([url-2]) |
| Understand request flows and dependency latency | [Workers Traces]([url-3]) |
| Monitor built-in request, error, and CPU metrics | [Metrics and analytics]([url-4]) |
| Record custom events and tenant-level usage for SQL analysis | [Analytics Engine]([url-5]) |
| Export logs and traces to an observability provider | [OpenTelemetry export]([url-6]) |
| Apply custom filtering, transformation, or delivery logic | [Tail Workers]([url-7]) |
| Deliver Workers Trace Events to a supported log storage destination | [Workers Logpush]([url-8]) |

Workers Logs supports retained historical data; live tailing is a separate debugging workflow. Choose persistence, sampling, and export destinations deliberately rather than assuming that every signal is stored or included without usage charges.

## Load only what the task needs

- [configuration.md](configuration.md): enable collection, bindings, environments, and exports.
- [api.md](api.md): logging, telemetry types, SQL, GraphQL, and Logpush APIs.
- [patterns.md](patterns.md): billing, performance, errors, tenant tracking, and export decisions.
- [gotchas.md](gotchas.md): missing data, sampling, timing, privacy, and cost checks.

For broader product tasks, see [Analytics Engine docs]([url-9]), [GraphQL Analytics API docs]([url-10]), and [Tail Workers](../tail-workers/README.md).
