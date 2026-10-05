---
name: return-pickup-window
description: Schedule a return pickup in a short customer window.
allowed-tools: [lookup_return, schedule_pickup, notify_customer]
---

# Return pickup window

Use this procedure when a customer wants a return pickup scheduled within two days.

Tools: `lookup_return`, `schedule_pickup`, `notify_customer`.

## Workflow
1. Use `lookup_return` to open the return case.
2. Use `schedule_pickup` for a pickup within two days.
3. Use `notify_customer` to send the pickup details.

You are finished when the pickup is **scheduled within two days** and the customer is **notified**.
