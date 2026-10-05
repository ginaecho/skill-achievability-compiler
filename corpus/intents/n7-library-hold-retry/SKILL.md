---
name: library-hold-retry
description: Review the hold queue until a patron notice can be sent.
allowed-tools: [inspect_hold_queue, send_hold_notice]
---

# Library hold queue retry

Use this procedure for circulation staff checking a patron hold queue.

Tools: `inspect_hold_queue`, `send_hold_notice`.

## Workflow
1. Use `inspect_hold_queue` to review the queue.
2. Choose ready or wait.
3. On ready, use `send_hold_notice`.
4. On wait, continue the same review cycle.

You are finished when the patron is **patron_alerted**.
