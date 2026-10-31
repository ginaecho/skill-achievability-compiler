# AI Search Pattern Routes

Choose retrieval-only search when your application displays chunks or handles generation itself; choose chat completions when AI Search should also generate the answer. Read [Search Workers binding]([url-1]) for both paths and streaming behavior.

| Task | Documentation |
|------|---------------|
| Isolate tenants using separate instances or a shared filtered instance | [Multitenancy]([url-2]) |
| Define built-in or custom metadata | [Metadata attributes]([url-3]) |
| Filter by metadata, combine conditions, or match a folder and subfolders | [Filtering]([url-4]) |
| Tune result count and relevance thresholds | [Result controls]([url-5]) |
| Resolve follow-up queries using conversation context | [Query rewriting]([url-6]) |
| Improve result ordering with a second model | [Reranking]([url-7]) |
| Customize generation and query-rewriting instructions | [System prompt]([url-8]) |

For tenant isolation, read the full multitenancy guide before choosing an approach. A lower-bound folder comparison alone does not establish a tenant boundary; use the documented filtering semantics.
