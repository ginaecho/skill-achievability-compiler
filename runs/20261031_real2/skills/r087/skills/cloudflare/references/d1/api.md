# D1 API Reference

Fetch the relevant API page before writing queries or assuming method signatures and return types.

| Task | Current documentation |
| --- | --- |
| Bind values and choose a query execution method | [Prepared statement methods]([url-1]) |
| Execute batches and understand transaction rollback; use database sessions | [D1 Database API]([url-2]) |
| Interpret results and query metadata | [Return objects]([url-3]) |
| Choose supported JavaScript values and TypeScript result types | [Workers Binding API]([url-4]) |
| Choose consistency constraints and carry bookmarks between requests | [Read replication and Sessions API]([url-5]) |
| Query from a server-side script outside Workers | [REST query API]([url-6]) |
| Handle query failures and transient errors | [Debug D1]([url-7]) and [retry queries]([url-8]) |
| Test database queries and apply migrations in tests | [Workers Vitest APIs: D1]([url-9]) |

Bind untrusted values with prepared statements; do not interpolate them into SQL. Parameters do not replace identifiers: choose dynamic table, column, or sort names from an application-controlled allowlist.

D1 sessions provide sequential consistency for replicated queries. They are not a way to extend query execution limits. Choose the starting constraint or bookmark from the application's consistency requirements using the replication guide.
