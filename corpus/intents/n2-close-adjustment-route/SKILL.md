---
name: close-adjustment-route
description: Route close posting through standard or adjustment handling.
allowed-tools: [prepare_adjustment_entry, post_adjusted_close, post_standard_close]
---

# Close adjustment route

Three participants take part: a **close reviewer**, a **controller**, and an **accountant**.

Tools: prepare_adjustment_entry, post_adjusted_close, post_standard_close.

## Workflow
1. The close reviewer chooses either adjustment or standard posting.
2. For adjustment posting, the controller uses `prepare_adjustment_entry`, then the accountant uses `post_adjusted_close`.
3. For standard posting, the accountant uses `post_standard_close`.

You are finished when the close is **posted**.
