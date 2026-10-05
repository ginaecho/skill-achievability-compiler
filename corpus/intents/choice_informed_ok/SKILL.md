---
name: triage-resolution-flow
description: Route a ticket to a simple or complex resolution path.
allowed-tools: [resolve_simple, resolve_complex]
---
# Triage and resolve a ticket

Use this procedure when a router chooses how a handler should resolve a ticket.

Tools: `resolve_simple`, `resolve_complex`.

Two participants take part: a **router** and a **handler**.

## Workflow
1. The router chooses the simple branch or the complex branch.
2. For the simple branch, the router sends `go_simple` to the handler, then the handler runs `resolve_simple`.
3. For the complex branch, the router sends `go_complex` to the handler, then the handler runs `resolve_complex`.

You are finished when the ticket is **triaged** and the ticket is **resolved**.
