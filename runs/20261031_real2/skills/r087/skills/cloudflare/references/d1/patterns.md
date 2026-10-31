# D1 Patterns & Best Practices

Use these guides to design the operation, then fetch [api.md](./api.md) for implementation references.

| Task | Current documentation |
| --- | --- |
| Design pagination, filters, joins, and aggregations | [Query a database]([url-1]) and [supported SQL]([url-2]) |
| Reduce scans and inspect query plans | [Use indexes]([url-3]) |
| Find queries in production to index or cache | [Find slow and expensive queries]([url-4]) |
| Batch writes or transform data | [Database API]([url-5]) and [limits]([url-6]) |
| Store and query event metadata | [Query JSON]([url-7]) |
| Evaluate a cache in front of D1 | [How KV works]([url-8]) |
| Choose shared or per-tenant databases | [D1 FAQs]([url-9]) and [limits]([url-6]) |
| Reduce read latency while preserving required consistency | [Read replication]([url-10]) |
| Plan point-in-time recovery or portable backups | [Time Travel]([url-11]) and [import/export]([url-12]) |

Keep result sets bounded and pagination ordering deterministic. Choose indexes from actual query plans. When splitting a large operation into batches, account for the loss of whole-operation atomicity across batches.

Authorize a tenant before selecting its database or rows; a request header alone is not proof of tenant membership. Application login sessions stored in tables are separate from D1's Sessions API.

Before caching reads, decide how stale data may be and how writes invalidate cached results. For replicated reads, choose session constraints and bookmark propagation based on read-after-write requirements rather than assuming every read sees the latest primary state.
