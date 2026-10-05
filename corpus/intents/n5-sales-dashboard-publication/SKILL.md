---
name: sales-dashboard-publication
description: Sales dashboard publication procedure.
allowed-tools: [ingest_sales_extract, shape_sales_metrics, publish_sales_dashboard]
---
# Sales dashboard publication

Use this procedure for the monthly sales dashboard.

Tools: `ingest_sales_extract`, `shape_sales_metrics`, `publish_sales_dashboard`.

## Workflow
1. Run `ingest_sales_extract` for the monthly source file.
2. Run `shape_sales_metrics` to prepare the measures.
3. Run `publish_sales_dashboard` for the dashboard.

You are finished when the sales dashboard is **published**.
