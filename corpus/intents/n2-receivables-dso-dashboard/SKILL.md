---
name: receivables-dso-dashboard
description: Publish an accounts receivable dashboard with a DSO target.
allowed-tools: [extract_receivables, compute_dso_metric, publish_ar_dashboard]
---

# Receivables DSO dashboard

Use this procedure for an AR analyst preparing the receivables dashboard.

Tools: extract_receivables, compute_dso_metric, publish_ar_dashboard.

## Workflow
1. Use `extract_receivables` to extract receivables.
2. Use `compute_dso_metric` to compute DSO.
3. Use `publish_ar_dashboard` to publish the dashboard.

You are finished when the AR dashboard is **published** with DSO below 45.
