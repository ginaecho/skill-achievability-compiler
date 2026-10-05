---
name: review-fix-recheck
description: Prepare a review fix and request a recheck.
allowed-tools: [fetch_changes, suggest_fix, apply_patchset, request_recheck]
---

# Review fix recheck

Use this procedure when a review assistant needs to turn review feedback into a recheck request.

Tools: `fetch_changes`, `suggest_fix`, `apply_patchset`, `request_recheck`.

## Workflow
1. Use `fetch_changes` to load the pull request changes.
2. Use `suggest_fix` after the changes are loaded.
3. Use `apply_patchset` after the fix is suggested.
4. Use `request_recheck` after the patchset is applied.

You are finished when the patchset is **applied** and the recheck is **requested**.
