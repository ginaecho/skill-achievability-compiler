---
name: planner-worker-collaboration
description: A planner delegates a task to a worker, who may ask a clarifying question before delivering. Use this for delegated work that sometimes needs clarification.
---

# Plan / worker collaboration

Two participants take part: a **planner** and a **worker**.

Your job is finished when the result has been **delivered**.

## Tools

Tools: answer, deliver, deliver_direct.

- `answer` marks the question **answered**.
- `deliver` requires the question **answered** and marks the result
  **delivered**.
- `deliver_direct` marks the result **delivered**.

## Workflow

1. The planner hands the task over and waits.
2. The worker decides, on its own, whether it needs clarification:
   - **ask branch** — the worker asks a clarifying question. The planner
     replies with `answer`, and the worker then delivers the result.
   - **direct branch** — the worker has everything it needs and delivers the
     result straight away with `deliver_direct`.
3. The planner takes what comes back.

The worker makes this choice internally; it does not announce which branch it
took. The planner simply waits for something to come back.
