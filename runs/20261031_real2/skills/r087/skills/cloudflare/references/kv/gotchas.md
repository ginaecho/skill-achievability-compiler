# KV Gotchas & Troubleshooting

Read the linked explanation before applying a workaround.

| Symptom or decision | Documentation and guidance |
|---------------------|----------------------------|
| Stale value after a write or delete | [How KV works]([url-1]): allow for eventual consistency; neither local read-after-write visibility nor a fixed global propagation deadline is guaranteed. |
| Newly created key still appears absent | [Read caching]([url-2]): missing-key lookups are cached too. Treat check-then-create as a race, not an atomic existence test. |
| Concurrent updates overwrite each other or writes are throttled | [Concurrent writes]([url-3]): retries do not make read-modify-write atomic. Use coordination when correctness depends on ordering. |
| Missing-value errors | [Read results]([url-2]): distinguish `null` from valid falsy values and distinguish absence from an operation failure. |
| Slow reads, large results, or excessive operations | [Read guidance]([url-2]): select result types and bulk reads to match the workload; increasing read cache lifetime trades freshness for cache reuse. |
| Unexpected empty listing page | [Pagination]([url-4]): use the completion flag and cursor, not page length, to determine whether to continue. |
| Data present in one environment but missing in another | [KV bindings]([url-5]) and [environments]([url-6]): check local versus remote storage and the selected namespace. |
| Size, operation, or write-rate failures | [Limits]([url-7]): retrieve current constraints before sizing values, batches, or retry policies. |
| Estimate costs or explain billing | [Pricing]([url-8]): check allowances, billable operations, storage, and bulk accounting for the actual workload. |

Confirm freshness and failure requirements before adding a cache or a permissive fallback; see [patterns.md](./patterns.md).
