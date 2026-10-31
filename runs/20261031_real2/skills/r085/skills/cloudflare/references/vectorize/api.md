# Vectorize API routes

Fetch the relevant section of the [Workers binding API]([url-1]) before writing calls or types.

| Task | Current documentation |
|------|-----------------------|
| Vector shape, binding, and generated TypeScript types | [Vectorize API]([url-1]) |
| Insert, upsert, retrieve by ID, delete, or inspect an index | [Operations]([url-2]) |
| Query by vector or ID; choose returned metadata, values, and scoring precision | [Query vectors]([url-3]) and [query options]([url-4]) |
| Filter by metadata, combine conditions, or use nested properties | [Metadata filtering]([url-5]) |
| Batch ingestion and select vector formats | [Insert vectors]([url-6]) and [current limits]([url-7]) |
| Manage indexes or vectors outside a Worker | [Wrangler commands]([url-8]) and [REST API]([url-9]) |

## Operation choices

- Choose insert when existing IDs should be preserved; choose upsert when they should be replaced. Upsert replaces the whole vector, including metadata, so provide the complete intended record.
- Request only the values and metadata the caller needs. Indexed metadata can omit fields or truncate strings; full metadata and vector values change query limits and latency. Fetch the current query options before choosing a result count.
- Treat accepted mutations and query visibility as separate events. Use current mutation guidance when implementing ingestion verification or read-after-write behavior.
