---
name: cash-forecast-distribution
description: Prepare a cash forecast and send the CFO digest.
allowed-tools: [ingest_bank_activity, forecast_cash_position, send_cfo_digest]
---

# Cash forecast distribution

Use this procedure for a finance manager preparing the cash forecast package.

Tools: ingest_bank_activity, forecast_cash_position, send_cfo_digest.

## Workflow
1. Use `ingest_bank_activity` to ingest bank activity.
2. Use `forecast_cash_position` to forecast the cash position.
3. Use `send_cfo_digest` to send the digest to the CFO.

You are finished when the cash position is **forecasted** and the CFO digest is **sent**.
