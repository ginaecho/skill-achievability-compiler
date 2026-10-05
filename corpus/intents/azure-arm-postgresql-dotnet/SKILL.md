---
name: postgresql-flexible-server-provisioning
description: Provision a PostgreSQL Flexible Server and database using the Azure Resource Manager SDK for .NET.
allowed-tools: [create_server, create_database]
---

# PostgreSQL Flexible Server Provisioning

Use this procedure when the desired outcome is actual Azure PostgreSQL Flexible Server resources created through the management plane.

Tools: `create_server`, `create_database`.

## Workflow

1. Prepare the resource group, region, server name, SKU, administrator settings, and PostgreSQL version for the ARM operation.
2. Use `create_server` to create the PostgreSQL Flexible Server resource.
3. Use `create_database` to create the application database inside that server.
4. Record the resulting server and database resource names for the author.

You are finished when the Flexible Server is **created** and the database is **created**.
