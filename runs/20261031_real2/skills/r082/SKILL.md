---
name: basin
description: Build and troubleshoot Cloudflare Basin analytics workflows with Basin Pipelines, Basin Catalog, and Basin SQL. Use for streaming data into R2 Iceberg tables, managing catalogs, or querying those tables; also use for requests using the former Data Platform, Pipelines, R2 Data Catalog, or R2 SQL names.
---

# Cloudflare Basin

Basin ingests and transforms events, manages Apache Iceberg tables in R2, and queries them with distributed SQL. Start with the [Basin overview]([url-1]) and retrieve the relevant current docs before implementing changes, especially for limits, pricing, permissions, and CLI syntax. While PR #33850 remains open, use the proposed pages in that PR if the new URLs have not been published.

## Rebrand

Cloudflare Data Platform is now **Basin**. Cloudflare Pipelines, R2 Data Catalog, and R2 SQL are now **Basin Pipelines**, **Basin Catalog**, and **Basin SQL**. Existing resources and configurations continue to work. The prior Wrangler command families also continue to work: `wrangler pipelines`, `wrangler r2 bucket catalog`, and `wrangler r2 sql`. Use the new Basin commands and documentation URLs in new guidance. Legacy API identifiers and metrics names may still use the old terms; check the current docs for deprecation details. The migration is documented in [cloudflare-docs PR #33850]([url-2]).

## Choose the workflow

| Need | Product | Reference | Current docs |
|------|---------|-----------|--------------|
| Receive events, transform rows, and deliver to R2 | Basin Pipelines | [Pipelines guide](references/pipelines/README.md) | [Basin Pipelines]([url-3]) |
| Manage Iceberg metadata, table maintenance, and engine access | Basin Catalog | [Catalog guide](references/catalog/README.md) | [Basin Catalog]([url-4]) |
| Query Iceberg tables with analytical SQL | Basin SQL | [SQL guide](references/sql/README.md) | [Basin SQL]([url-5]) |

Typical flow: Basin Pipelines → Basin Catalog tables in R2 → Basin SQL or a compatible external engine. Begin with the [Basin getting started guide]([url-6]) for an end-to-end setup.

The proposed Wrangler command families are `wrangler basin pipelines`, `wrangler basin catalog`, and `wrangler basin sql`. Basin SQL uses `WRANGLER_BASIN_SQL_AUTH_TOKEN`; its REST query path is `/basin-sql/query/{BUCKET}`. Check the installed Wrangler version and current reference pages before running commands because the migration is ongoing.

## Skill feedback

If the user reports that this skill gave incorrect or outdated guidance, or is missing information, read [references/skill-feedback.md](references/skill-feedback.md).
