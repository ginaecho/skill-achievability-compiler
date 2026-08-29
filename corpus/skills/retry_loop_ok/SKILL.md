---
name: retry-search-then-deliver
description: Search in a loop until results are found, then deliver the answer. Use this when searches may need several attempts before they succeed.
---

# Retry search until found, then deliver

A single **worker** carries out this skill.

Your job is finished when the question is **answered**.

## Tools

Tools: search, deliver.

- `search` marks the information **found**.
- `deliver` requires the information **found** and marks the question
  **answered**.

## Workflow

Loop:

1. Search for the information.
2. The worker looks at what came back and picks one of two ways forward:
   - **retry** — nothing turned up, so go back to the start of the loop.
   - **found** — the information is there, so leave the loop.

Once the loop has been left:

3. Deliver the answer.

This is tail-recursive retry: the block either goes round again or is done
with, and being done with it is what reaches the goal.
