---
name: fan-out-research
description: Fan research out to helper subagents spawned at run time, then deliver a report. Use this for research wide enough to split across several helpers.
---

# Fan out research to freshly spawned subagents

A **planner** carries out this skill, together with helper subagents it
creates while it runs.

Your job is finished when the **report has been delivered**.

## Tools

Tools: deliver.

## Workflow

1. Break the research question into parts. How many parts there are depends on
   the question — it is not fixed in advance.
2. **Spawn a fresh helper subagent for each part**, at run time. The number of
   helpers is decided during execution, not before it.
3. Collect what the helpers send back.
4. Deliver the report.

The set of participants is not known before the run starts: the planner
creates new ones as it goes, and there is no bound on how many it may create.
