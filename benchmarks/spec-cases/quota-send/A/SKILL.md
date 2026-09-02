---
name: quota-send
description: Send the campaign within the budget the skill states; the send must be recorded by the too
---
# Quota Send

Your job is finished when the campaign is **sent at a cost below 100**.

## Tools

Tools: send_batch.

`send_batch` only ever sends campaigns costing under 100.

Each tool is a script: `python tools/<tool>.py`.

## Workflow

1. Send it with `send_batch`.
