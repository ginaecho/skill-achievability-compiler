# AI Gateway Features

Fetch the relevant guide before setting feature flags, headers, limits, or billing behavior.

| Task | Current documentation |
|------|-----------------------|
| Enable caching, set TTLs, bypass the cache, or choose a custom cache key | [Caching]([url-1]) |
| Control request volume with fixed or sliding limits | [Rate limiting]([url-2]) |
| Enforce cost budgets | [Spend limits]([url-3]) |
| Evaluate and enforce content policies | [Guardrails setup]([url-4]) and [usage considerations]([url-5]) |
| Detect sensitive data in prompts and responses | [DLP setup]([url-6]) |
| Choose provider keys or Cloudflare billing | [BYOK]([url-7]) and [Unified Billing]([url-8]) |
| Configure provider data retention for Unified Billing | [Zero Data Retention]([url-9]) |
| Configure log collection, payload storage, and retention | [Logging]([url-10]) |
| Export logs | [Workers Logpush]([url-11]) |
| Attach request metadata for tracking and routing | [Custom metadata]([url-12]) |
| Override model costs | [Custom costs]([url-13]) |
| Check supported providers, quotas, or pricing | [Provider guides]([url-14]), [limits]([url-15]), and [pricing]([url-16]) |

Choose cache keys only for requests whose responses may safely be shared. Decide what prompt and response data may be stored before enabling logging; do not infer a provider's retention policy from gateway log settings.

For conditional policies and fallbacks, see [dynamic routing](./dynamic-routing.md).
