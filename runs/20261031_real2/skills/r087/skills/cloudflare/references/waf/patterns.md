# WAF Patterns

Choose the workflow that matches the requested outcome, then retrieve its current examples. Make rule scope explicit and review the affected traffic before enforcement.

| Outcome | Documentation |
|---------|---------------|
| Apply managed protection to a zone | [Deploy managed rules]([url-1]) |
| Change a managed rule's behavior or evaluate it with logging | [Override a managed ruleset]([url-2]) |
| Enforce an application-specific request policy | [Create a custom rule]([url-3]) |
| Use attack detection in a request policy | [Attack score semantics and availability]([url-4]) |
| Protect a login or API endpoint from excessive requests | [Rate limiting API examples]([url-5]) and [counting parameters]([url-6]) |
| Exempt narrowly identified traffic from selected protections | [Available skip options]([url-7]) |
| Adjust protection after a false positive | [Managed rules troubleshooting]([url-8]) |

For a false positive, identify the matching rule and request scope before choosing an exception or override. Keep the adjustment as narrow as the evidence supports. For combined protections, check [WAF phases]([url-9]) before deciding where an exception belongs.

Use [configuration.md](configuration.md) to select the deployment method and [api.md](api.md) to preserve existing rules while changing it.
