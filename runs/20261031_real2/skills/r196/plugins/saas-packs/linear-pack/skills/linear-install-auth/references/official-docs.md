# Linear Official Documentation Snapshot

Verified against Linear first-party documentation and official npm metadata on 2026-09-11. Recheck schema fields, OAuth scopes and grants, rate-limit headers, webhook event types, package releases, plan entitlements, import behavior, and commercial terms before changing production because those surfaces are dynamic.

## Primary sources

- [GraphQL API]([url-1])
- [Rate limiting]([url-2])
- [OAuth 2.0]([url-3])
- [Webhooks]([url-4])
- [TypeScript SDK]([url-5])
- [Fetching and modifying data]([url-6])
- [SDK errors]([url-7])
- [Advanced SDK usage]([url-8])
- [SDK webhooks]([url-9])
- [Pagination]([url-10])
- [Filtering]([url-11])
- [Deprecations]([url-12])
- [SDK 1.x to 2.x migration]([url-13])
- [SCIM]([url-14])
- [Members and roles]([url-15])
- [Audit log]([url-16])
- [Exporting data]([url-17])
- [Importing guidance]([url-18])
- [CLI importer]([url-19])

## Skill focus

This reference supports `linear-install-auth`. Apply only the contracts needed for that workflow, verify the current workspace plan and app settings, and treat live schema introspection plus the installed generated SDK types as the authority for fields available to the authenticated actor.

## Verified baseline

- GraphQL endpoint: `[url-20]`. Personal API keys use the raw Authorization value; OAuth access tokens use Bearer.
- API key budgets: 2,500 requests and 3,000,000 complexity points per user per hour. OAuth budgets: 5,000 requests and 2,000,000 points per user or app user per hour. Unauthenticated budgets: 600 requests and 100,000 points per IP per hour. A single query is capped at 10,000 points; endpoint-specific limits can be lower.
- GraphQL rate limiting is an HTTP 400 response with `extensions.code: RATELIMITED`. Always inspect the GraphQL `errors` array even when HTTP is 200.
- Webhooks require public HTTPS, exact raw-body HMAC-SHA256 verification, HTTP 200 within five seconds, and deduplication by `Linear-Delivery`. Failed delivery retries occur after one minute, one hour, and six hours.
- All OAuth apps moved to refresh tokens on 2026-04-01. For CI and scheduled automation, Linear recommends acquiring client-credentials tokens per run rather than copying a persistent access token.
- npm reported `@linear/sdk` 95.0.0 with Node.js `>=18.x` on 2026-09-11. Pin the resolved lockfile and recheck the current package before upgrades.
- SCIM 2.0 and 90-day audit logs are Enterprise capabilities. Obtain the SCIM base URL from workspace settings; never hard-code a guessed connector endpoint.
