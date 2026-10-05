---
name: monitor-oncall-alert
description: Handle an alert based on a monitor-selected urgency path.
allowed-tools: [handle_now, handle_later]
---
# Route and handle an alert

Use this procedure when a monitor chooses an alert urgency and an oncall participant handles it.

Tools: `handle_now`, `handle_later`.

Two participants take part: a **monitor** and an **oncall**.

## Workflow
1. The monitor decides whether the alert is urgent or routine.
2. On the urgent path, the oncall runs `handle_now`.
3. On the routine path, the oncall runs `handle_later`.

You are finished when the alert is **classified** and **handled**.
