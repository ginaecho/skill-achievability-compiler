---
name: ticket-route-selector
description: Route a ticket to a handler and resolve it with the selected fix.
allowed-tools: [fix_a, fix_b]
---
# Route a ticket to a handler

Use this procedure when a router selects a route and a handler applies the matching fix.

Tools: `fix_a`, `fix_b`.

Two participants take part: a **router** and a **handler**. The router agent's declared behaviour selects route a and sends `go_a`.

## Workflow
1. The contract lets the router choose route a, send `go_a`, and have the handler run `fix_a`.
2. The contract lets the router choose route b, send `go_b`, and have the handler run `fix_b`.
3. The router agent's declared behaviour selects route a and sends `go_a`.

You are finished when the ticket is **routed** and **resolved**.
