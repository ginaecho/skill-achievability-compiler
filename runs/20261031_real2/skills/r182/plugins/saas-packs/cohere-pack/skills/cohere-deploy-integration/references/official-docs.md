# Cohere Official Documentation Snapshot

Verified against Cohere primary documentation, the official SDK repositories, and package registries on 2026-09-11. Recheck the live model catalog, deprecation schedule, pricing, and rate-limit page before changing a production workload because those surfaces are intentionally dynamic.

## SDK and authentication

- [Create a v2 client]([url-1])
- [Official TypeScript SDK]([url-2])
- [Official Python SDK]([url-3])
- [API key types and limits]([url-4])
- [Teams and roles]([url-5])

## Models and inference

- [Live model catalog]([url-6])
- [Command A+]([url-7])
- [Chat API]([url-8])
- [Embed API]([url-9])
- [Rerank models]([url-10])
- [Rerank API]([url-11])
- [Tool use]([url-12])
- [Streaming]([url-13])
- [Safety modes]([url-14])

## Lifecycle and operations

- [API v1 to v2 migration]([url-15])
- [Deprecations]([url-16])
- [OpenAI compatibility]([url-17])
- [Going live]([url-18])
- [Error reference]([url-19])
- [Cohere status]([url-20])
- [Pricing]([url-21])
- [Privacy policy]([url-22])
- [Cloud-platform compatibility]([url-23])

## Pinned interpretation

- New integrations use API v2 clients: `CohereClientV2` in TypeScript and `cohere.ClientV2` in Python. On 2026-09-11, the registry releases were `cohere-ai@8.1.0` and `cohere==7.1.1`; pin a compatible range and retain the resolved lockfile version.
- Resolve deployable models from the live catalog or Models API. `command-a-plus-05-2026`, `embed-v4.0`, `rerank-v4.0-pro`, and `rerank-v4.0-fast` were live reference candidates on the review date, not permanent aliases.
- API v2 requires `model` for Chat, Embed, Rerank, and Classify; Embed also requires `embedding_types`. Chat history lives in `messages`, and tools use JSON Schema.
- Managed `/v1/connectors`, `connectors` on Chat v1, Generate, Summarize, Classify, and legacy fine-tuning were listed as deprecated. In v2, implement retrieval or web search as application-owned tools.
- Evaluation and production limits differ by endpoint and model. Some newer Chat models require a sales-approved production arrangement. Treat the live limits page and response behavior as authoritative.
- Cohere Teams expose Owner and User roles, but application authorization, per-tenant budgets, and least-privilege runtime keys remain the customer's responsibility.
- The public privacy policy says enterprise customer-data commitments are contract-specific. Do not infer retention, residency, or training terms from generic marketing copy; bind production controls to the signed agreement.
