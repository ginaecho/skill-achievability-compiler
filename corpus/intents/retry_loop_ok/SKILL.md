---
name: retry-search-deliver-answer
description: Repeat search attempts as needed and deliver the answer after results are found.
allowed-tools: [search, deliver]
---

# Retry search and deliver an answer

A single **worker** carries out this procedure, choosing whether to keep searching or move to delivery after each attempt.

Tools: `search`, `deliver`.

## Workflow

1. Run `search` for the requested information.
2. The worker chooses `retry` to repeat the search or `found` to leave the search loop.
3. After choosing `found`, use `deliver` to provide the answer.

You are finished when the answer is **delivered**.
