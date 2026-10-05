---
name: fan-out-ledger-update
description: Spawn helpers for distributed work and update the ledger afterward.
allowed-tools: [update_ledger]
---

# Fan out work, then update the ledger

A **planner** coordinates helper agents created at run time and records the outcome afterward.

Tools: `update_ledger`.

## Workflow

1. Spawn helper agents at run time for the work.
2. Collect the helpers' completed work.
3. Record the outcome with `update_ledger`.

You are finished when the ledger is **updated**.
