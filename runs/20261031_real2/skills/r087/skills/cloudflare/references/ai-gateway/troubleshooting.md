# AI Gateway Troubleshooting

Identify the request path and whether the failure comes from gateway access, upstream provider authentication, or request policy before changing credentials or retry behavior. A status code alone does not establish the failing layer.

| Symptom or task | Current documentation |
|-----------------|-----------------------|
| Authentication or provider errors, timeouts, DLP failures, or unexpected cache behavior | [Troubleshooting]([url-1]) |
| Gateway authentication failure | [Authenticated Gateway]([url-2]) and [REST API authentication]([url-3]) |
| Provider key or billing mismatch | [BYOK]([url-4]), [Unified Billing]([url-5]), and the [provider guide]([url-6]) |
| Rate limits or repeated failures | [Rate limiting]([url-7]) and [request handling]([url-8]) |
| Unexpected cache hit or miss, including streaming behavior | [Caching]([url-9]) |
| Missing logs, collection overrides, or storage limits | [Logging]([url-10]) and [limits]([url-11]) |
| Inspect headers, request metadata, usage, or export logs | [Header glossary]([url-12]), [custom metadata]([url-13]), [analytics]([url-14]), and [Logpush]([url-15]) |
| Dynamic route failure | [Dynamic route usage]([url-16]) |

Check the existing SDK and gateway retry settings together before adding another retry loop. Follow [SDK integration](./sdk-integration.md) when an endpoint or model format is suspect.
