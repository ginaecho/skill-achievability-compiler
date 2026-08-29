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

The handler waits for any of three labels and acts on whichever arrives:

- `go_simple` — resolve the ticket with `resolve_simple`.
- `go_complex` — resolve the ticket with `resolve_complex`.
- `go_escalate` — hand the ticket to a human reviewer.

The contract above never sends `go_escalate`; the handler is simply prepared
for a label this router will not use. Being ready for more than the contract
sends is safe — the handler still covers every path the router can actually
take.
