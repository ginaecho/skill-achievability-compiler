# Workers AI Patterns

Use direct generation when the supplied context fits the selected model and retrieval is unnecessary. Use RAG when answers need grounding in a document corpus or relevant passages must be selected from larger data; decide from the actual model context budget rather than a fixed token threshold.

| Task | Documentation |
|------|---------------|
| Build retrieval with Workers AI, Vectorize, and document storage | [RAG tutorial]([url-1]) |
| Stream responses or integrate tool calling in an SDK application | [AI SDK integration]([url-2]) |
| Constrain generated JSON | [JSON mode]([url-3]) |
| Add caching, retries, or model fallbacks | [Caching]([url-4]), [request handling]([url-5]), and [dynamic routing]([url-6]) |

Treat tutorial models as examples; select models using the [model criteria](./README.md#choose-a-model). For RAG, embed queries and documents with compatible models and match the index dimensions to the embeddings. Budget for retrieval and embedding work as well as generation.

Before adding a fallback model, verify that it can satisfy the same schema, context, and tool requirements. For retry decisions, distinguish transient failures from invalid inputs or configuration using the [error and limit references](./gotchas.md).
