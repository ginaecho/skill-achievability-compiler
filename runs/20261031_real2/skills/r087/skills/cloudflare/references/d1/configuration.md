# D1 Configuration

Read the task's documentation before adding bindings or running database commands. Confirm the database and environment being targeted, particularly when applying migrations or importing data.

| Task | Current documentation |
| --- | --- |
| Create a database and attach a Worker binding | [Getting started]([url-1]) |
| Configure binding fields and multiple databases | [Wrangler D1 configuration]([url-2]) |
| Separate staging and production databases | [D1 environments]([url-3]) |
| Create, track, and apply schema migrations | [Migrations]([url-4]) |
| Look up CLI flags for management, execution, and exports | [D1 Wrangler commands]([url-5]) |
| Develop against local database state | [Local development]([url-6]) |
| Generate binding types | [Workers TypeScript]([url-7]) |
| Choose an ORM or query builder, including Drizzle | [D1 community projects]([url-8]) (follow the integration's current setup guide) |
| Import or export SQL data | [Import and export data]([url-9]) |
| Enable replicas and use them through sessions | [Read replication]([url-10]) |

Local migrations and data do not automatically update a remote database. Test against a separate staging database before a production migration. Naming another binding `DB_REPLICA` does not configure replica routing; follow the replication guide.
