# Cloudflare Pages Functions

Use this reference for server-side behavior in an existing Pages project. For new applications, follow the Workers recommendation in the [Pages framework guidance]([url-1]).

| Task | Documentation |
| --- | --- |
| Identify filesystem routes and invocation boundaries | [Routing]([url-2]) |
| Implement request handlers | [API reference]([url-3]) |
| Understand generated Worker output | [Advanced mode]([url-4]) |

Inspect whether the project uses a Functions directory or framework-generated advanced mode before selecting a routing approach. Fetch current documentation for signatures, supported bindings, configuration, and examples.

## In This Reference

- [api.md](./api.md) — handlers, context, middleware, and assets
- [configuration.md](./configuration.md) — bindings, environments, types, and local development
- [patterns.md](./patterns.md) — request ownership and shared logic
- [gotchas.md](./gotchas.md) — route, binding, and runtime investigation

See [Pages](../pages/README.md) for builds and deployment decisions.
