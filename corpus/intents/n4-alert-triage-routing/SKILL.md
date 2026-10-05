---
name: alert-triage-routing
description: Route an alert using the dispatch decision.
allowed-tools: [ack_page, open_major_case]
---

# Alert triage routing

Use this procedure when an incoming alert needs a minor or major handling path.

Two participants take part: a **dispatcher** and a **responder**.
Tools: `ack_page`, `open_major_case`.

## Workflow
1. The dispatcher chooses the minor route or the major route.
2. For the minor route, the dispatcher sends `route_minor` to the responder, then the responder uses `ack_page`.
3. For the major route, the dispatcher sends `route_major` to the responder, then the responder uses `open_major_case`.

You are finished when the incident is **routed**.
