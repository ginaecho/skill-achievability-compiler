# AI Gateway Configuration

Choose the request path before configuring authentication: Cloudflare REST inference, a Workers binding, and provider-native gateway endpoints have different requirements. Gateway access does not by itself define which upstream credentials or billing source a request uses.

| Task | Current documentation |
|------|-----------------------|
| Send a first request and locate the account/gateway identifiers | [Getting started]([url-1]) |
| Create, update, or delete a gateway; use the default gateway | [Manage gateways]([url-2]) |
| Manage gateways programmatically | [Gateway management API]([url-3]) |
| Protect gateway access and choose token permissions for the endpoint | [Authenticated Gateway]([url-4]) and [REST API authentication]([url-5]) |
| Configure Wrangler and an AI binding | [Workers AI binding setup]([url-6]) and [binding methods]([url-7]) |
| Store provider keys, select aliases, or diagnose missing credentials | [Bring Your Own Keys]([url-8]) |
| Use Cloudflare billing or determine which credentials take precedence | [Unified Billing]([url-9]) |
| Supply provider credentials with each request | [Provider guides]([url-10]) |

Keep credentials out of source code. Use the chosen endpoint's documentation for headers and permissions instead of reusing an authentication recipe from another endpoint. Check credential precedence before changing an existing BYOK or billing setup.

For SDK selection, see [SDK integration](./sdk-integration.md); for policy settings, see [features](./features.md).
