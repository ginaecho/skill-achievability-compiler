---
name: refund-ledger-update
description: Issue a customer refund and update the ledger.
allowed-tools: [lookup, refund, update_ledger]
---

# Refund ledger update

Use this procedure to complete a customer refund and record it in the ledger.

Tools: lookup, refund, update_ledger.

## Workflow
1. Use `lookup` to find the customer order.
2. Use `refund` to issue the refund for that order.
3. Use `update_ledger` to record the refund in the ledger.

You are finished when the refund is **issued** and the ledger is **updated**.
