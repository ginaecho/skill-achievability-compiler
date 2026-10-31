# D1 Gotchas & Troubleshooting

Use current documentation to diagnose the failure before changing query or database configuration.

| Symptom or question | What to check |
| --- | --- |
| Missing table, query exception, or constraint error | [Debug D1]([url-1]); verify the target binding, environment, and applied [migrations]([url-2]) |
| Boolean, date, or other binding type mismatch | [Workers Binding API type conversion]([url-3]) and [SQL support]([url-4]) |
| Foreign key failure during writes or migrations | [Foreign key enforcement and deferral]([url-5]) |
| Slow or expensive database, excessive rows read or written, or finding which databases and queries cost the most | [Find slow and expensive queries]([url-6]) with `cf sql query` or `wrangler d1 insights` (API tokens need **Account Analytics Read**); then [indexes and query plans]([url-7]) |
| Query duration, statement, storage, or account limits | [Current limits]([url-8]) |
| Unexpected usage charges or plan assumptions | [Pricing]([url-9]); [find the databases and queries that cost the most]([url-6]) |
| Stale reads after a write | [Sessions, bookmarks, and read replication]([url-10]) |
| Transient query failures | [Retry guidance]([url-11]); check idempotency before retrying writes |
| Import/export failure or unsupported data | [Import/export behavior and limitations]([url-12]) |
| Local and deployed databases differ | [Local development]([url-13]) and [environment configuration]([url-14]) |

Continue to bind untrusted SQL values as described in [api.md](./api.md). Do not treat SQL injection as a recoverable database error or assume retries correct invalid queries.
