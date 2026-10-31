# Bindings API Reference

Fetch the relevant documentation before choosing method signatures, binding types, or type-generation settings.

| Task | Current documentation |
| --- | --- |
| Access bindings in handlers, entrypoint classes, or imported `env` | [Bindings and environment access]([url-1]) |
| Generate environment and runtime types; configure TypeScript or migrate from `@cloudflare/workers-types` | [Workers TypeScript]([url-2]) |
| Use framework-specific environment access | [Hono on Workers]([url-3]) (follow the framework's linked documentation) |
| Read, write, delete, and list KV keys | [KV Workers API]([url-4]) |
| Read, write, delete, and list R2 objects | [R2 Workers API]([url-5]) |
| Prepare and bind SQL statements or execute batches | [D1 Workers Binding API]([url-6]) |
| Address Durable Objects and call their methods | [Durable Objects API]([url-7]) |
| Send queue messages | [Queues JavaScript APIs]([url-8]) |
| Run model inference | [Workers AI bindings]([url-9]) |
| Call another Worker using HTTP or typed RPC | [Service bindings]([url-10]) and [RPC TypeScript]([url-11]) |
| Find other product binding APIs, including Browser, mTLS, rate limiting, and Workflows | [Current binding catalog]([url-1]) |

Regenerate types after configuration changes and use the selected environment's configuration. Follow the current TypeScript setup for the project's toolchain instead of hardcoding a generated declaration path or maintaining a handwritten binding interface. Types describe the expected bindings; they do not provision resources or prove the deployed environment is configured correctly.
