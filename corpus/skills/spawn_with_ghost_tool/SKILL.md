---
name: fan-out-then-update-ledger
description: Fan work out to helper subagents spawned at run time, then record the result in the ledger. Use this when distributed work must be reconciled into the books.
---

# Fan out, then update the ledger

A **planner** carries out this skill, together with helper subagents it
creates while it runs.

Your job is finished when the **ledger has been updated**.

## Tools

No tools are granted to this skill.

## Workflow

1. **Spawn helper subagents** at run time to carry out the work. The number of
   helpers is decided during execution, not before it.
2. Collect what comes back.
3. Record the outcome in the accounting ledger via `update_ledger`.

The books must reflect the work that was done, so the ledger entry is not
optional.
