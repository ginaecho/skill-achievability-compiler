# Static Assets Binding API

Read the binding reference before implementing calls. Check the configured binding name and use the project's existing environment types.

| Task | Documentation |
|------|---------------|
| Forward a request or fetch a specific asset | [Runtime API reference]([url-1]) |
| Understand how binding requests apply HTML and fallback settings | [Binding fetch behavior]([url-1]) and [HTML handling]([url-2]) |
| Run authorization or transform content before serving | [Run your Worker script first]([url-3]) |
| Inspect default MIME, cache, and validation headers | [Default headers]([url-4]) |
| Add or override response headers | [Custom headers and Worker-response caveat]([url-5]) |
| Fetch assets imported by Vite | [Vite asset features]([url-6]) |

When selecting a different asset, construct a full URL using the incoming request as the base. Preserve the returned status and headers when transforming a response; do not collapse every unsuccessful response into an application 404.

See [configuration.md](configuration.md) for bindings and [patterns.md](patterns.md) for routing choices.
