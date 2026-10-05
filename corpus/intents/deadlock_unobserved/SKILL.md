---
name: plan-worker-delivery
description: Coordinate planner and worker actions to deliver a task result.
allowed-tools: [answer, deliver, deliver_direct]
---
# Plan and deliver a task result

Use this procedure when a worker evaluates whether the result needs planner input or direct delivery.

Tools: `answer`, `deliver`, `deliver_direct`.

Two participants take part: a **planner** and a **worker**.

## Workflow
1. The worker decides which of two paths to use.
2. On the planner-input path, the planner runs `answer`, then the worker runs `deliver`.
3. On the direct path, the worker runs `deliver_direct`.

You are finished when the task result is **assessed** and **delivered**.
