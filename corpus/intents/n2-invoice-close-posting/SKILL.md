---
name: invoice-close-posting
description: Post invoice accruals and send a close summary.
allowed-tools: [import_invoice_batch, match_purchase_orders, post_accruals, send_close_summary]
---

# Invoice close posting

Use this procedure during month-end invoice close.

Tools: import_invoice_batch, match_purchase_orders, post_accruals, send_close_summary.

## Workflow
1. Use `import_invoice_batch` to bring in the invoice batch.
2. Use `match_purchase_orders` to match the purchase orders.
3. Use `post_accruals` to post the accrual entries.
4. Use `send_close_summary` to send the close summary.

You are finished when accruals are **posted** and the close summary is **sent**.
