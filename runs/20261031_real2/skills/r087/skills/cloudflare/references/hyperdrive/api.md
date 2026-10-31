# Hyperdrive API and drivers

Start with [README.md](./README.md) and [configuration.md](./configuration.md). Fetch the selected guide before writing connection or query code; use its current supported package version and compatibility settings.

## Driver and binding routes

| Task | Official documentation |
|------|------------------------|
| PostgreSQL with node-postgres (`pg`), including binding connection string and parameterized queries | [node-postgres]([url-1]) |
| PostgreSQL with tagged-template queries and Postgres.js driver options | [Postgres.js]([url-2]) |
| MySQL with binding connection properties and Worker-specific driver options | [mysql2]([url-3]) |
| Check database features, prepared statements, and library compatibility | [Supported databases and features]([url-4]) |
| Generate binding and runtime TypeScript types | [Workers TypeScript]([url-5]) |

Keep an existing supported driver when it fits the application. Choose by database engine and library integration needs; do not infer cache behavior from a driver's prepared-statement setting. Fetch [query caching]([url-6]) for cache eligibility and freshness controls.

## ORMs and query builders

| Task | Official documentation |
|------|------------------------|
| Use Drizzle with PostgreSQL | [PostgreSQL Drizzle guide]([url-7]) |
| Use Drizzle with MySQL | [MySQL Drizzle guide]([url-8]) |
| Use Prisma with PostgreSQL | [Prisma guide]([url-9]) |
| Assess another query builder, including Kysely | [Postgres.js integration notes]([url-2]) and [database compatibility]([url-4]), then the library's current dialect documentation |

An ORM still uses a database driver and inherits its Worker connection constraints. Keep clients scoped to the invocation using [connection lifecycle]([url-10]). When a library owns SQL for authentication or other fresh reads, pass a client using a cache-disabled configuration as described in [query caching]([url-6]).
