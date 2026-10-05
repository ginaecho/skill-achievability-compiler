---
name: transcript-turnaround-target
description: Set and send a transcript turnaround target.
allowed-tools: [intake_transcript_request, set_transcript_window, send_transcript_status]
---

# Transcript turnaround target

Use this procedure when a records officer promises a transcript status within 5 business days.

Tools: `intake_transcript_request`, `set_transcript_window`, `send_transcript_status`.

## Workflow
1. Use `intake_transcript_request` to enter the request.
2. Use `set_transcript_window` for a turnaround within 5 business days.
3. Use `send_transcript_status` to send the status.

You are finished when the status is **status_sent** and business_days is at most 5.
