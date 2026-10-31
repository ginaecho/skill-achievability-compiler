# WAF API Reference

Read the matching workflow before writing API calls or translating them into the project's installed SDK. Retrieve identifiers from the target account or zone; do not reuse example IDs.

| Task | Documentation |
|------|---------------|
| Inspect the entry point and add custom rules | [Create a custom rule via API]([url-1]) |
| Discover managed rulesets and deploy them | [Deploy managed rules via API]([url-2]) |
| Create rate limits with the current request schema | [Create a rate limiting rule via API]([url-3]) |
| Select counting characteristics, expressions, periods, and mitigation behavior | [Rate limiting parameters]([url-4]) |
| Replace a ruleset deliberately or choose an additive operation | [Update or deploy a ruleset]([url-5]) |
| Construct expressions using supported fields, operators, and functions | [Rules language]([url-6]) |
| Choose actions and understand terminating behavior | [Actions reference]([url-7]) |
| Override managed rules, tags, or a ruleset | [Managed ruleset overrides]([url-8]) |
| Choose exactly what a skip rule bypasses | [Skip options]([url-9]) |

For an addition, prefer the workflow's operation that adds a rule to an existing ruleset. When replacing a ruleset, include every rule that must remain; review the resulting rule list before applying it. See [gotchas.md](gotchas.md) for scope and evaluation checks.
