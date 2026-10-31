# Cloudflare Workers KV

Use KV for read-heavy configuration, preferences, and application caches that tolerate stale data. Read [how KV works]([url-1]) before choosing it: reads are eventually consistent, including cached missing keys, and immediate visibility is not guaranteed even in the location of a write.

For atomic updates or coordination, consider [Durable Objects]([url-2]); for relational queries, [D1](../d1/); for large objects, [R2](../r2/). Use the [storage comparison]([url-3]) to choose based on requirements.

Read the current documentation for the task before implementing. Use the [KV documentation index]([url-4]) to discover additional guides; these files preserve task routes rather than copies of APIs, commands, or numeric limits.

## Start here

- [Get started]([url-5]): create a namespace, bind it, and read and write data.
- [configuration.md](./configuration.md): bindings, environments, types, local development, CLI, and REST access.
- [api.md](./api.md): reads, writes, metadata, deletion, bulk operations, and pagination.
- [patterns.md](./patterns.md): caching, sessions, key design, versioning, and fallback decisions.
- [gotchas.md](./gotchas.md): stale reads, concurrent writes, missing values, performance, limits, and pricing.
