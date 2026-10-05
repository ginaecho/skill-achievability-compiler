---
name: return-inspection-dispatch
description: Create a return case and bring in an inspector for results.
allowed-tools: [create_return_case, assign_inspection_task, record_inspection_result]
---

# Return inspection dispatch

Use this procedure when a return needs an inspection participant added during the case flow. Two participants take part over the flow: a **returns_coordinator** and a **return_inspector**.

Tools: `create_return_case`, `assign_inspection_task`, `record_inspection_result`.

## Workflow
1. The **returns_coordinator** uses `create_return_case`.
2. Add a **return_inspector** participant during the flow.
3. The **returns_coordinator** uses `assign_inspection_task`.
4. The **return_inspector** uses `record_inspection_result`.

You are finished when the return case is **created** and the inspection result is **recorded**.
