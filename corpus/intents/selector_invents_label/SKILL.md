---
name: routed-ticket-handler
description: Route a ticket between two handler paths and resolve it.
allowed-tools: [fix_a, fix_b]
---

# Route a ticket to a handler

Two participants take part: a **router** and a **handler**. The router chooses the path, and the handler resolves the ticket for the chosen path.

Tools: `fix_a`, `fix_b`.

## Workflow

1. For path A, the router sends `go_a` to the handler, and the handler runs `fix_a`.
2. For path B, the router sends `go_b` to the handler, and the handler runs `fix_b`.
3. The router's declared behavior selects path C and sends `go_c`.

You are finished when the ticket is **resolved**.
