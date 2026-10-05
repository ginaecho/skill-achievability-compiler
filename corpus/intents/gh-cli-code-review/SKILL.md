---
name: gh-cli-static-code-review
description: Review a GitHub CLI pull request using the local diff and repository contract.
allowed-tools: [read_pr_diff, read_repo_contract, deliver_review]
---

# GitHub CLI Static Code Review

Use this procedure when a gh CLI pull request needs a static review grounded in the local diff and repository rules.

Tools: `read_pr_diff`, `read_repo_contract`, `deliver_review`.

## Workflow

1. Use `read_pr_diff` to inspect the pull request changes.
2. Use `read_repo_contract` to load the repository contract and applicable guidance.
3. Compare the diff with the issue, PR description, tests, and command behavior expectations.
4. Use `deliver_review` to provide grouped findings and honest test notes.

You are finished when the repository contract is **read**, the pull request diff is **read**, and the static review is **delivered**.
