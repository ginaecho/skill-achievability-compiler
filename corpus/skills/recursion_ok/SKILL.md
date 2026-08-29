---
name: retry-search-then-answer
description: Retry a search until results are found, then deliver the answer. Use this when a single search attempt may come back empty.
---

# Retry search until found, then answer

A single **worker** carries out this skill.

Your job is finished when the **answer has been delivered**.

## Tools

Tools: search, deliver.

## Workflow

1. Search for the information.
2. If nothing was found, search again.
3. Once the information has been found, deliver the answer.

The retry is genuinely optional: the search may succeed on the first attempt
and the worker delivers immediately. The loop has a real exit — finding the
information — and delivery happens on that exit.
