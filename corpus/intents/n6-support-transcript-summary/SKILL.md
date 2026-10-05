---
name: support-transcript-summary
description: Summarize a support transcript and post it to the case.
allowed-tools: [fetch_conversation, summarize_conversation, post_case_summary]
---

# Support transcript summary

Use this procedure after a long support conversation needs a concise case summary.

Tools: `fetch_conversation`, `summarize_conversation`, `post_case_summary`.

## Workflow
1. Use `fetch_conversation` to retrieve the case conversation.
2. Use `summarize_conversation` to prepare the case summary.
3. Use `post_case_summary` to add the summary to the case.

You are finished when the summary is **posted** to the support case.
