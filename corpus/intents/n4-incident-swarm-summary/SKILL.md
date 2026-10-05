---
name: incident-swarm-summary
description: Start a responder participant and summarize findings.
allowed-tools: [aggregate_findings]
---

# Incident swarm summary

Use this procedure when an incident coordinator brings in a responder during the run and produces a summary.

Participants begin with a **coordinator**; a **responder** participant is started during the workflow.
Tools: `aggregate_findings`.

## Workflow
1. Start a responder participant during the workflow.
2. Use `aggregate_findings` to prepare the incident summary.

You are finished when the summary is **ready**.
