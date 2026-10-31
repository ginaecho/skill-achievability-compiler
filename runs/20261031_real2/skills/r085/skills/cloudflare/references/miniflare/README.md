# Miniflare

Miniflare provides programmatic control of local Workers simulation. Read the linked documentation before choosing APIs, configuration, or a migration path.

## Choose the testing tool

| Need | Start here |
|------|------------|
| Unit tests that execute in the Workers runtime | [Workers Vitest setup]([url-1]) |
| Integration tests against built Workers | [Integration test harness]([url-2]) |
| Low-level simulator control for a custom harness | [Miniflare testing guide]([url-3]) |
| Binding access from a Node.js process | [Wrangler getPlatformProxy]([url-4]) |

For interactive local development, use the project's Wrangler or Cloudflare Vite workflow. Direct Miniflare is useful when the higher-level testing tools do not expose the control needed.

## Read for the task

- [Get started]([url-5]) — installation, scripts, lifecycle, and event dispatch.
- [API routing](./api.md) — events and access to local resources.
- [Configuration](./configuration.md) — modules, bindings, compatibility, and multiple Workers.
- [Testing patterns](./patterns.md) — runtime choice, mocking, and test lifecycle.
- [Troubleshooting and migrations](./gotchas.md) — build/configuration differences and existing test suites.
