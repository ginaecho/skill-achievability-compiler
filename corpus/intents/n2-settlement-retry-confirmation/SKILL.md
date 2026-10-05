---
name: settlement-retry-confirmation
description: Review and submit a settlement batch until confirmation is recorded.
allowed-tools: [review_settlement_batch, submit_settlement_run]
---

# Settlement retry confirmation

Use this procedure for a settlement operator confirming a payment batch.

Tools: review_settlement_batch, submit_settlement_run.

## Workflow
1. Use `review_settlement_batch` to review the settlement batch.
2. Start the settlement retry cycle.
3. In each cycle, use `submit_settlement_run`, check for settlement confirmation, and continue the cycle when another pass is needed.

You are finished when the settlement is **confirmed**.
