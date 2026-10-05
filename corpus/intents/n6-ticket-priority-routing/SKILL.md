---
name: ticket-priority-routing
description: Route a support ticket by priority and resolve it.
allowed-tools: [classify_ticket, resolve_standard, resolve_escalated]
---

# Ticket priority routing

Use this procedure to classify a customer support ticket and route it for the right resolution path. Two participants take part: a **triage_agent** and a **case_owner**.

Tools: `classify_ticket`, `resolve_standard`, `resolve_escalated`.

## Workflow
1. The **triage_agent** uses `classify_ticket` to classify the ticket.
2. The **triage_agent** chooses the standard or escalated path.
3. For standard tickets, the **triage_agent** sends `route_standard` to the **case_owner**, then the **case_owner** uses `resolve_standard`.
4. For escalated tickets, the **triage_agent** sends `route_escalated` to the **case_owner**, then the **case_owner** uses `resolve_escalated`.

You are finished when the ticket is **resolved**.
