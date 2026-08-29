---
name: refund-customer
description: Issue a refund to a customer and record it in the ledger. Use this when a customer is owed money back on an order.
---

# Refund a customer

Your job is finished when the customer has been **refunded** and the **ledger
has been updated** to record it.

## Tools

Tools: lookup, refund.

- `lookup` marks the **order found**.
- `refund` requires the **order found** and marks the customer **refunded**.

## Workflow

1. Look up the customer's order.
2. Issue the refund against that order.
3. Record the outcome in the accounting ledger via `update_ledger`, so the
   books match what was actually paid out.

Both halves matter: money that never reaches the ledger leaves the accounts
wrong.
