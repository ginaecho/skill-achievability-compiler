---
name: refund-ledger-close
description: Process a refund record and close the return case.
allowed-tools: [locate_return, process_refund_record, close_case]
---

# Refund ledger close

Use this procedure when a return case needs the customer refund issued and the case closed.

Tools: `locate_return`, `process_refund_record`, `close_case`.

## Workflow
1. Use `locate_return` to open the return case.
2. Use `process_refund_record` to issue the refund.
3. Use `close_case` to close the case.

You are finished when the refund is **issued** and the return case is **closed**.
