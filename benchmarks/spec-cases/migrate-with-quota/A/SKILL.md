---
name: migrate-with-quota
description: Migrate the tenants within the budget the skill states; the migration must be recorded by 
---
# Migrate With Quota

Your job is finished when the tenants are **migrated at a cost below 500**.

## Tools

Tools: migrate_incremental.

`migrate_incremental` only ever migrates at a cost under 500.

Each tool is a script: `python tools/<tool>.py`.

## Workflow

1. Migrate them with `migrate_incremental`.
