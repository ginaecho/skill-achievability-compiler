---
name: route-ticket-prompt
description: Resolve a ticket through the routing protocol.
---

# Resolve a routed ticket

Two participants take part: a **router** and a **handler**.

Your job is finished when the ticket is **resolved**.

## Tools

Required tools: fix_a, fix_b.

- `fix_a` marks the ticket **resolved**.
- `fix_b` marks the ticket **resolved**.

## Contract

- **route A** - the router sends `go_a`; the handler uses `fix_a`.
- **route B** - the router sends `go_b`; the handler uses `fix_b`.

## Declared router behavior

The router selects route C and sends `go_c`.
