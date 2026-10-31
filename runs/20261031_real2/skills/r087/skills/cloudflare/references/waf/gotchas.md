# WAF Gotchas

Use observed requests and the deployed ruleset definitions to diagnose behavior before changing protection.

| Symptom or decision | Documentation to read |
|---------------------|-----------------------|
| A rule executes earlier or later than expected | [WAF phases and account/zone order]([url-1]) and [terminating actions]([url-2]) |
| A skip rule leaves a protection active | [Skip scope, phases, products, and logging]([url-3]) |
| Updating a ruleset removes unrelated rules | [Ruleset replacement semantics]([url-4]) |
| An expression fails to parse | [Rules language elements]([url-5]) |
| Score-based rules match unexpected traffic | [Attack score meaning, special values, and plan availability]([url-6]) |
| Managed overrides conflict | [Override precedence and scope]([url-7]) |
| Legitimate traffic is blocked, or attacks reach the origin | [False-positive and false-negative investigation]([url-8]) |
| Rate limits affect shared-IP users or count unexpected requests | [Characteristics, NAT support, and counting expressions]([url-9]) |
| API creation fails or the request body is unclear | [Custom rule creation]([url-10]), [managed deployment]([url-11]), or [rate limit creation]([url-12]) |

Check account versus zone scope, rule position, and the action that actually handled the request. For rate limiting, inspect matching and counting criteria separately. Avoid broad exceptions as a shortcut for diagnosing a single false positive.

Return to [api.md](api.md) for operations and [configuration.md](configuration.md) for deployment ownership.
