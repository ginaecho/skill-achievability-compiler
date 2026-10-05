---
name: fan-out-research-report
description: Spawn helper agents for research fan-out and deliver the finished report.
allowed-tools: [deliver]
---

# Fan out research and deliver a report

A **planner** coordinates helper agents created at run time for a research task.

Tools: `deliver`.

## Workflow

1. Break the research work into parts.
2. Spawn helper agents at run time to cover those parts.
3. Collect the helpers' findings.
4. Use `deliver` to provide the final report.

You are finished when the report is **delivered**.
