---
name: tolerant-ticket-handler
description: Resolve a routed ticket while accepting declared handler labels.
allowed-tools: [resolve_simple, resolve_complex]
---
# Resolve a routed ticket

Use this procedure when a router chooses a simple or complex path and a handler applies the corresponding resolution.

Tools: `resolve_simple`, `resolve_complex`.

Two participants take part: a **router** and a **handler**. The handler accepts `go_simple`, `go_complex`, or `go_escalate`; `go_escalate` also resolves through `resolve_complex`.

## Workflow
1. If the router chooses simple, it sends `go_simple` and the handler runs `resolve_simple`.
2. If the router chooses complex, it sends `go_complex` and the handler runs `resolve_complex`.
3. Under the declared handler behaviour, `go_simple` maps to `resolve_simple`, while `go_complex` and `go_escalate` map to `resolve_complex`.

You are finished when the routed ticket is **selected** and **resolved**.
