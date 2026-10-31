# KV API Reference

Read the relevant API page before implementing; it defines current options, result shapes, supported bulk operations, and constraints.

| Task | Documentation |
|------|---------------|
| Read one or several keys; choose text, JSON, binary, or stream results | [Read key-value pairs]([url-1]) |
| Read metadata with values; tune read caching or coalesce related keys | [Read guidance]([url-1]) |
| Write values and metadata; set absolute expiration or a relative lifetime | [Write key-value pairs]([url-2]) |
| Delete a key | [Delete key-value pairs]([url-3]) |
| Enumerate keys, filter by prefix, and paginate | [List keys]([url-4]) |
| Access namespaces or perform bulk operations outside a Worker | [KV REST API]([url-5]) and [Wrangler KV commands]([url-6]) |

Handle missing values explicitly: JavaScript reads return `null` for absent keys; valid stored values can be falsy. Choose defaults separately from how you handle request failures.

For pagination, follow the returned cursor until `list_complete` is true, even if a page has no keys. Preserve the original prefix on subsequent calls. Listing returns key information, not stored values; use the listing guide to decide whether metadata avoids additional reads.

Use [gotchas.md](./gotchas.md) for consistency and contention decisions before adding retries or read-after-write verification.
