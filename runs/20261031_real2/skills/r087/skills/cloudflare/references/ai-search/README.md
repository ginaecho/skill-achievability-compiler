# Cloudflare AI Search

Use AI Search for managed content indexing and retrieval, with optional answer generation. Start with [How AI Search works]([url-1]).

## Choose the right product

- **Managed search or RAG over your content:** AI Search.
- **Custom embeddings and vector-index management:** [Vectorize](../vectorize/README.md).
- **Model inference without a managed retrieval pipeline:** [Workers AI](../workers-ai/README.md).

For freshness requirements, read [Syncing]([url-2]) for your data source before choosing an architecture. Use the current [limits and pricing]([url-3]) instead of assuming a fixed indexing interval or account limit.

## Find the right documentation

Read the linked page before implementing; these references route to the maintained documentation instead of copying API examples or configuration.

| Task | Start here |
|------|------------|
| Build a new Worker integration | [Workers binding quick start]([url-4]) |
| Choose an API or maintain an existing integration | [API routes](api.md) |
| Connect data, configure indexing, or manage environments | [Configuration routes](configuration.md) |
| Choose retrieval, generation, or tenant isolation patterns | [Pattern routes](patterns.md) |
| Diagnose indexing, authentication, filters, or limits | [Troubleshooting routes](gotchas.md) |

Existing `[host-1].autorag()` integrations can continue to work. Use the [migration guide]([url-5]) when upgrading; migration is not required just to maintain an existing integration.
