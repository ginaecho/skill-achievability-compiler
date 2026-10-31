# Cloudflare WAF

Use this reference for managed protection, custom request policies, rate limiting, and investigation of blocked traffic. Read the relevant developer documentation before implementing; it owns schemas, expressions, ruleset IDs, phase order, and plan availability.

| Task | Start here |
|------|------------|
| Choose and enable WAF protections | [Get started]([url-1]) |
| Deploy managed protection | [Managed rules deployment]([url-2]) |
| Match application-specific requests | [Custom rules]([url-3]) |
| Limit request volume | [Rate limiting]([url-4]) |
| Understand score-based detection | [Attack score]([url-5]) |
| Diagnose blocked or unmitigated requests | [Managed rules troubleshooting]([url-6]) |

Identify the target account or zone and inspect existing rules before planning a change. Keep the requested traffic scope explicit, especially for exceptions and account-wide deployments.

## Reading Order

1. [configuration.md](configuration.md) — deployment method and existing configuration.
2. [api.md](api.md) — API workflows and expression references.
3. [patterns.md](patterns.md) — choose a protection or exception workflow.
4. [gotchas.md](gotchas.md) — diagnose ordering, scope, and false positives.
