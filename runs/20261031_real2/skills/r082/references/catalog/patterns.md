# Basin Catalog Patterns

Choose the engine based on the project's existing runtime and workload, then retrieve its current connection example.

| Need | Starting point |
|------|----------------|
| Python catalog operations and ingestion without a Spark deployment | [PyIceberg]([url-1]) |
| Existing Spark ETL and distributed table processing | [PySpark]([url-2]) |
| Connect an existing SQL engine | [Engine configuration guides]([url-3]) |
| Query through Cloudflare's serverless SQL service | [Basin SQL](../sql/) |
| Stream events into tables | [Basin Pipelines patterns](../pipelines/patterns.md) |

Use the discovered Catalog URI and Warehouse name from [configuration](configuration.md). Match dependencies to the installed engine and the current guide instead of adopting a universal pinned Spark/Iceberg combination.

Plan ingestion, query, and maintenance responsibilities together. Prefer [automatic table maintenance]([url-4]) when it meets the workload; align retention with time-travel needs before enabling expiration. For engine-specific partitioning, schema evolution, or manual procedures, consult that engine's linked upstream documentation and verify behavior on representative data.

When multiple writers share a table, design recovery around the actual failed operation and the engine's commit semantics. Reproduce conflicts and ensure retries do not duplicate application work. See [API selection](api.md) and [troubleshooting](gotchas.md).
