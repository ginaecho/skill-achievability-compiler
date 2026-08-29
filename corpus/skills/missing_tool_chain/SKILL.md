---
name: refund-customer
description: Issue a refund to a customer and record it in the ledger. Use this when a customer is owed money back on an order.
---

# Refund a customer

Your job is finished when the **refund has been issued** and the **ledger has
been updated** to record it.

## Tools

Tools: lookup_order, issue_refund.

## Workflow

1. Look up the customer's order.
2. Issue the refund against that order.
3. Update the accounting ledger with the refund via `update_ledger`, so the
   books match what was actually paid out.

Both halves matter: a refund that never reaches the ledger leaves the accounts
wrong.
