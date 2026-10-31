# Vectorize troubleshooting routes

Fetch current documentation before diagnosing a numeric limit, API error, or delayed mutation. Do not infer batch sizes or result limits from old snippets.

| Symptom or decision | What to check | Current documentation |
|---------------------|---------------|-----------------------|
| A write succeeded but search has not changed | Mutations are asynchronous; acceptance does not guarantee query visibility | [Insert, upsert, and delete semantics]([url-1]) |
| Ingestion is slow or a batch is rejected | Batch size depends on the interface; inspect throughput and payload constraints | [Write throughput]([url-2]) and [limits]([url-3]) |
| Query count is rejected or metadata is incomplete | Returned values and metadata affect query limits; indexed metadata can be truncated | [Query options]([url-4]) |
| Metadata filters return no matches | Confirm field type, operators, nesting, and index creation; re-upsert data written before the metadata index existed | [Metadata filtering]([url-5]) |
| Query has no matches or poor relevance | Check embedding model and dimensions, metric, namespace, filters, and mutation visibility | [Query vectors]([url-6]) and [index configuration]([url-7]) |
| Existing IDs or metadata behave unexpectedly on update | Insert preserves existing IDs; upsert replaces the full vector and metadata | [Mutation semantics]([url-1]) |
| Capacity or model output no longer fits | Check current limits and model output dimensions; changing dimensions or metric requires another index | [Limits]([url-3]) and [create indexes]([url-7]) |

For changes to embedding providers or tenant boundaries, also read [pattern decisions](patterns.md).
