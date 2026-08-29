---
name: triage-then-handle
description: Route a support ticket down a simple or complex path and resolve it. Use this when tickets need triage before a handler works on them.
---

# Triage then handle

Two participants take part: a **router** and a **handler**.

Your job is finished when the **ticket is resolved**.

## Tools

Tools: resolve_simple, resolve_complex.

## Contract

1. The router inspects the ticket and picks one of two paths:
   - **simple path** — the router tells the handler `go_simple`, and the
     handler resolves the ticket with `resolve_simple`.
   - **complex path** — the router tells the handler `go_complex`, and the
     handler resolves the ticket with `resolve_complex`.

## Declared handler behaviour

The handler waits for `go_simple`, then resolves the ticket with
`resolve_simple`.

That is the whole of the handler's declared behaviour. It does not wait for
`go_complex` and has nothing to do if that is what arrives.
