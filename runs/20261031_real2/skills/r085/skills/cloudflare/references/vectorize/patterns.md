# Vectorize pattern routes

| Task | Current documentation |
|------|-----------------------|
| Generate and query Workers AI embeddings | [Vectorize and Workers AI]([url-1]) |
| Query with embeddings from OpenAI | [OpenAI integration]([url-2]) |
| Choose embedding dimensions and distance metric | [Create indexes]([url-3]) |
| Build a retrieval-augmented generation application | [Workers AI RAG tutorial]([url-4]) |
| Link search results to source documents | [Vector metadata]([url-5]) |
| Partition vectors by tenant | [Namespaces]([url-6]) and [namespace versus metadata filtering]([url-7]) |
| Combine similarity search with categorical or range filters | [Metadata filtering]([url-8]) |
| Ingest or update vectors in batches | [Insert vectors]([url-9]) and [limits]([url-10]) |

## Embedding and retrieval decisions

Keep ingestion and query embeddings compatible: use the same model and preprocessing, and extract the individual vector from the provider's documented response shape. Fetch the selected model's current documentation for dimensions and input requirements.

For RAG, store a reliable reference to the source content and request the metadata needed to resolve it. Handle missing or deleted source documents before passing retrieved context to generation.

## Tenant scope

Namespaces and metadata filters narrow searches; they do not authenticate the caller. Derive the permitted tenant scope from trusted identity and enforce it on every relevant read and write, including ID-based retrieval and deletion. Do not assume a namespace query option protects other operations.

Choose namespace or metadata partitioning based on the required query scope and current limits. Both narrow the search space; avoid assuming metadata filtering happens after vector search. If tenant IDs are stored in metadata, create the corresponding metadata index before ingestion.
