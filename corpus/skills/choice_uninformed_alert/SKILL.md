---
name: route-alert
description: Route an alert to on-call handling based on urgency.
---

# Route an alert

Two participants take part: a **monitor** and an **oncall**.

Your job is finished when the alert is **handled**.

## Tools

Required tools: handle_now, handle_later.

- `handle_now` marks the alert **handled**.
- `handle_later` marks the alert **handled**.

## Workflow

The monitor privately chooses one path:

- **urgent** - the oncall handles the alert with `handle_now`.
- **routine** - the oncall handles the alert with `handle_later`.

The oncall receives no message identifying the selected path.
