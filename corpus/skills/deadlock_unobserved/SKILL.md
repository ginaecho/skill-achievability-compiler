---
name: planner-worker-collaboration
description: A planner delegates a task to a worker, who may ask a clarifying question before delivering. Use this for delegated work that sometimes needs clarification.
---

# Plan / worker collaboration

Two participants take part: a **planner** and a **worker**.

Your job is finished when the **task result has been delivered**.

## Tools

Tools: answer, deliver, deliver_direct.

## Workflow

1. The planner hands the task to the worker and waits for the result.
2. The worker decides, on its own, whether it needs clarification:
   - **ask branch** — the worker asks a clarifying question. The planner
     answers it with `answer`, and the worker then delivers the result.
   - **deliver branch** — the worker has everything it needs and delivers the
     result directly with `deliver_direct`.
3. The planner receives the result.

The worker makes this choice internally; it does not announce which branch it
took. The planner simply waits for the result to come back.
