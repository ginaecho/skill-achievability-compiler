---
name: research-then-answer
description: Research a question and deliver an answer to the user, sending status notes along the way. Use this for research requests where the worker keeps the user informed while working.
---

# Research then answer (with status notes)

Two participants take part: a **worker** and the **user**.

Your job is finished when the question is **answered**.

## Tools

Tools: search, deliver.

- `search` marks the question **searched**.
- `deliver` requires the question **searched** and marks it **answered**.

## Workflow

1. The worker tells the user `status_note`, to say it is starting.
2. Search for the information needed.
3. The worker tells the user `status_note2`, to say it is nearly there.
4. Deliver the answer to the user.

The status notes are a detour, not a step towards the goal: sending them, or
not sending them, must not change whether the question eventually gets an
answer. Both paths are acceptable.
