---
name: retry-search-then-answer
description: Retry a search until results are found, then deliver the answer. Use this when a single search attempt may come back empty.
---

# Retry search until found, then answer

A single **worker** carries out this skill.

Your job is finished when the question is **answered**.

## Tools

Tools: search, deliver.

- `search` marks the information **found**.
- `deliver` requires the information **found** and marks the question
  **answered**.

## Workflow

1. Search for the information.
2. Once the information has been found, deliver the answer.

The retry is genuinely optional. A first attempt that comes back empty is
simply repeated until something turns up; an attempt that succeeds outright
lets the worker move straight on. Either way the second step is reached, and
that is the step that finishes the job.
