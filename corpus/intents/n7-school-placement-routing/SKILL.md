---
name: school-placement-routing
description: Route a student placement to the registrar.
allowed-tools: [place_standard_seat, place_support_seat]
---

# School placement routing

Use this procedure when a placement lead selects the placement path for a student record.

Tools: `place_standard_seat`, `place_support_seat`.

Two participants take part: a **placement_lead** and a **registrar**.

## Workflow
1. The placement lead chooses the standard branch or the support branch.
2. For the standard branch, the placement lead sends `standard_path` to the registrar, then the registrar runs `place_standard_seat`.
3. For the support branch, the placement lead sends `support_path` to the registrar, then the registrar runs `place_support_seat`.

You are finished when the student record is **student_placed**.
