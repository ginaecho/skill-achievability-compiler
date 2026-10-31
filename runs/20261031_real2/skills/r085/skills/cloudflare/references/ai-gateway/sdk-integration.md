# AI Gateway SDK Integration

Choose an integration that matches the application's runtime and required API shape. Fetch its guide before installing packages or writing requests; model identifiers, SDK options, and gateway headers belong in the docs.

| Integration task | Current documentation |
|------------------|-----------------------|
| New single-model HTTP calls or OpenAI-compatible clients | [REST API]([url-1]) |
| Vercel AI SDK, provider adapters, and fallback providers | [Vercel AI SDK integration]([url-2]) |
| Preserve OpenAI-native endpoints with the OpenAI SDK, Python, or HTTP | [OpenAI provider guide]([url-3]) |
| Preserve Anthropic-native requests | [Anthropic provider guide]([url-4]) |
| Use another provider or a framework's configurable provider endpoint | [Provider guides]([url-5]) — match the framework's expected API shape to the provider endpoint |
| Configure Workers AI and an AI binding | [Binding setup]([url-6]) |
| Call Workers AI or third-party models from a Worker; use gateway methods | [Workers binding methods]([url-7]) |
| Set request metadata, caching, or other gateway headers | [Header glossary]([url-8]) |
| Invoke a dynamic route | [Dynamic route usage]([url-9]) |

The [legacy Unified API]([url-10]) is deprecated for single-model calls, but dynamic routes still require its compatibility endpoint. Do not migrate a dynamic route to the REST inference endpoint as though it were a single-model call.

Confirm [gateway authentication and provider credentials](./configuration.md) separately, including the selected path's BYOK and billing behavior.
