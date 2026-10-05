---
name: monthly-revenue-pack
description: Monthly revenue pack procedure.
allowed-tools: [refresh_semantic_model, render_revenue_report, distribute_revenue_pack]
---
# Monthly revenue pack

Use this procedure for monthly revenue BI reporting.

Tools: `refresh_semantic_model`, `render_revenue_report`, `distribute_revenue_pack`.

## Workflow
1. Run `refresh_semantic_model` for the revenue dataset.
2. Run `render_revenue_report` for the management view.
3. Run `distribute_revenue_pack` for the stakeholder pack.

You are finished when the revenue pack is **distributed**.
