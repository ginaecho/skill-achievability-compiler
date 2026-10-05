---
name: cosmosdb-sql-resource-provisioning
description: Provision a Cosmos DB account, SQL database, and container with the Azure Resource Manager SDK for .NET.
allowed-tools: [create_account, create_database, create_container]
---

# Cosmos DB SQL Resource Provisioning

Use this procedure when Cosmos DB SQL API resources should be created through the ARM management plane.

Tools: `create_account`, `create_database`, `create_container`.

## Workflow

1. Confirm the account name, region, consistency, database name, container name, and partition key design for the requested SQL API resources.
2. Use `create_account` to create the Cosmos DB account.
3. Use `create_database` to create the SQL database under the account.
4. Use `create_container` to create the SQL container under the database.
5. Summarize the created resource hierarchy.

You are finished when the Cosmos DB account is **created**, the SQL database is **created**, and the SQL container is **created**.
