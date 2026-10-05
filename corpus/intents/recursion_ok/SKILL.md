---
name: search-then-deliver-answer
description: Search for information and deliver the answer once it is found.
allowed-tools: [search, deliver]
---

# Search and deliver an answer

A single **worker** carries out this procedure for a question that needs a researched answer.

Tools: `search`, `deliver`.

## Workflow

1. Try `search` to find the needed information.
2. Once the information is found, use `deliver` to provide the answer.

You are finished when the answer is **delivered**.
