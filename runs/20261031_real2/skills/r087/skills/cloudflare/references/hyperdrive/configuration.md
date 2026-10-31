# Hyperdrive configuration

See [README.md](./README.md) for the retrieval workflow. Fetch the relevant guide before creating or changing resources; use current configuration fields and CLI syntax from these sources.

| Task | Official documentation |
|------|------------------------|
| Create the first configuration and bind it to a Worker | [Get started]([url-1]) |
| Create, inspect, update, or delete configurations; set cache or pool options | [Wrangler commands]([url-2]) |
| Generate TypeScript types from Worker configuration | [Workers TypeScript]([url-3]) |
| Connect a private database using the recommended Workers VPC route | [Workers VPC integration]([url-4]) |
| Maintain a private database connection using Tunnel and Access | [Tunnel integration]([url-5]) |
| Configure database network access | [Firewall and networking]([url-6]) |
| Configure server verification or client certificates | [SSL/TLS certificates]([url-7]) |
| Rotate origin database credentials | [Credential rotation]([url-8]) |
| Configure cache freshness or separate cached and fresh-read bindings | [Query caching]([url-9]) |
| Budget origin connections across configurations | [Tune connection pooling]([url-10]) |
| Choose local database access or remote Hyperdrive testing | [Local development]([url-11]) |
| Place compute near a regional database | [Placement Hints]([url-12]) |

## Setup decisions

- Identify the database engine, provider, and network path first. The [PostgreSQL]([url-13]) and [MySQL]([url-14]) indexes route to provider-specific instructions.
- For private connectivity, choose Workers VPC or the existing Tunnel/Access integration before configuring credentials. Follow the selected guide's prerequisites and TLS guidance.
- Decide which reads may be stale before selecting cache settings. Multiple configurations against one database contribute to its total origin connection usage.
- Local direct database access does not exercise Hyperdrive pooling or caching. Use the local-development guide's remote option when verifying those behaviors, and identify the database that option targets before running writes.

See [api.md](./api.md) for drivers and [gotchas.md](./gotchas.md) for diagnosis.

## Place compute near the database

Fetch [Workers placement]([url-15]) before configuring a database-backed Worker. For multiple sequential queries to one regional database, prefer an explicit region hint over waiting for Smart Placement to learn from traffic. Hyperdrive pools origin connections; its binding does not automatically configure Worker placement.

- Establish the database's actual cloud provider and region from provider metadata or the user.
- If location is missing, ask for the provider and region. For unknown or multiple back-end locations, use [Smart Placement]([url-16]).
