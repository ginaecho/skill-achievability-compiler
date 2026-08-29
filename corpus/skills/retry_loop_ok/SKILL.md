---
name: retry-search-then-deliver
description: Search in a loop until results are found, then deliver the answer. Use this when searches may need several attempts before they succeed.
---

# Retry search until found, then deliver

A single **worker** carries out this skill.

Your job is finished when the **answer has been delivered**.

## Tools

Tools: search, deliver.

## Workflow

Loop:

1. Search for the information.
2. If nothing was found, go back to step 1 and search again.
3. If the information was found, exit the loop and deliver the answer.

The loop has a genuine exit branch — finding the information — and delivery
happens on that branch. This is tail-recursive retry: the loop either goes
round again or leaves, and leaving is what reaches the goal.
