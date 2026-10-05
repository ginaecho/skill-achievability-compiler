---
name: router-handler-resolution
description: Route a ticket and resolve it through the handler.
allowed-tools: [resolve_simple, resolve_complex]
---
# Route and resolve a ticket

Use this procedure when a router may choose a simple or complex ticket path for a handler.

Tools: `resolve_simple`, `resolve_complex`.

Two participants take part: a **router** and a **handler**. The handler waits for `go_simple` from the router and then runs `resolve_simple`.

## Workflow
1. The router may choose the simple path and send `go_simple`, after which the handler runs `resolve_simple`.
2. The router may choose the complex path and send `go_complex`, after which the handler runs `resolve_complex`.
3. The handler follows its declared behaviour by waiting for `go_simple` and then running `resolve_simple`.

You are finished when the ticket is **routed** and **resolved**.
