---
name: research-answer-flow
description: Research a request, share progress notes, and deliver the answer.
allowed-tools: [search, deliver]
---
# Research and deliver an answer

Use this procedure when a worker needs to research a request and complete the answer for a user.

Tools: `search`, `deliver`.

Two participants take part: a **worker** and a **user**.

## Workflow
1. The worker sends the user the `status_note` message.
2. The worker runs `search` to gather the material.
3. The worker sends the user the `status_note2` message.
4. The worker runs `deliver` to provide the researched answer.

You are finished when the answer is **researched** and the response is **answered**.
