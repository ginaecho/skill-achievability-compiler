---
name: alert-triage-dashboard
description: Alert triage dashboard procedure.
allowed-tools: [build_urgent_dashboard, build_routine_dashboard]
---
# Alert triage dashboard

Use this procedure when alert analytics need either an urgent or routine dashboard.

Tools: `build_urgent_dashboard`, `build_routine_dashboard`.

Two participants take part: an **analyst** and a **builder**.

## Workflow
1. The analyst chooses the urgent branch or the routine branch.
2. For the urgent branch, the analyst sends `urgent_slice` to the builder, then the builder runs `build_urgent_dashboard`.
3. For the routine branch, the analyst sends `routine_slice` to the builder, then the builder runs `build_routine_dashboard`.

You are finished when the dashboard is **ready**.
