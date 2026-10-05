---
name: quarterly-liquidity-brief
description: Prepare a treasury liquidity brief with a runway target.
allowed-tools: [pull_cash_positions, calculate_runway, publish_treasury_brief]
---

# Quarterly liquidity brief

Use this procedure for a treasury analyst preparing the quarter-end liquidity note.

Tools: pull_cash_positions, calculate_runway, publish_treasury_brief.

## Workflow
1. Use `pull_cash_positions` to gather current cash balances.
2. Use `calculate_runway` to compute runway days for the quarter.
3. Use `publish_treasury_brief` to publish the treasury brief.

You are finished when the treasury brief is **published** and runway days are at least 90.
