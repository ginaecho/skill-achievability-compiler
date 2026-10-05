---
name: claim-response-window
description: Send an administrative claim response within the target window.
allowed-tools: [open_claim_file, send_claim_response]
---

# Claim response window

Use this procedure when a benefits coordinator must answer an administrative claim file within 5 days.

Tools: `open_claim_file`, `send_claim_response`.

## Workflow
1. Use `open_claim_file` to open the claim file.
2. Use `send_claim_response` to send the response within 5 days.

You are finished when the response is **response_sent** and response_days is at most 5.
