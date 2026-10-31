# Cloudflare AI Gateway

Use AI Gateway to observe and control requests to AI providers through caching, rate limiting, logging, and routing.

Fetch the linked documentation before choosing endpoints, authentication headers, SDK options, model names, or limits. Keep implementation details in the current docs.

## Choose a task

| Task | Reference |
|------|-----------|
| Create a gateway or choose authentication and provider credentials | [Configuration](./configuration.md) |
| Integrate an SDK, direct HTTP, or a Worker binding | [SDK integration](./sdk-integration.md) |
| Configure caching, rate limits, security, billing, or logging | [Features](./features.md) |
| Add fallbacks, conditional routing, or traffic splits | [Dynamic routing](./dynamic-routing.md) |
| Diagnose failed requests, caching, or missing logs | [Troubleshooting](./troubleshooting.md) |

For new single-model calls, start with the [REST API]([url-1]) or [Workers bindings]([url-2]), depending on the runtime. Preserve provider-native integrations when their API shape is needed; use the corresponding [provider guide]([url-3]).

The [legacy Unified API]([url-4]) is deprecated for single-model calls but remains required for dynamic routes. Check the task before changing an existing endpoint.

Gateway authentication and upstream provider credentials are separate concerns. Choose the endpoint first, then follow its authentication and billing requirements in [configuration](./configuration.md).

## Related references

- [Workers AI](../workers-ai/README.md) — model inference.
- [Agents SDK documentation]([url-5]) — stateful agents.
- [Vectorize](../vectorize/README.md) — vector search.
