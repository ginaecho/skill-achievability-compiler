# Vectorize configuration routes

| Task | Current documentation |
|------|-----------------------|
| Create an index, choose dimensions and metric | [Create indexes]([url-1]) |
| Bind an index to a Worker, develop, deploy, and verify queries | [Introduction to Vectorize]([url-2]) |
| Configure bindings and generate types | [Binding and TypeScript guidance]([url-3]) |
| Create, list, or delete metadata indexes | [Metadata filtering]([url-4]) and [Wrangler commands]([url-5]) |
| Manage indexes and vectors through the CLI | [Wrangler commands]([url-5]) |
| Upload NDJSON and batch ingestion | [Insert vectors]([url-6]) |
| Check capacity, payload, namespace, or batch constraints | [Limits]([url-7]) |

## Configuration decisions

Confirm the embedding model, output dimensions, and distance metric before provisioning: dimensions and metric cannot be changed in place. Plan a new index and re-embedding where needed when changing models.

Create metadata indexes before ingesting vectors that must be filterable. If adding one to an existing dataset, plan to re-upsert the affected vectors after index creation.

Choose metadata granularity around actual queries. For range filters over high-cardinality fields, consider buckets that preserve the application's required precision; do not bucket identifiers used for exact matches. Fetch the [cardinality guidance]([url-8]) before designing the schema.
