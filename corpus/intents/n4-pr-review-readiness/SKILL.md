---
name: pr-review-readiness
description: Review a pull request and mark it ready.
allowed-tools: [scan_diff, post_review, mark_ready]
---

# Pull request review readiness

Use this procedure for a reviewer preparing a pull request for merge.

Tools: `scan_diff`, `post_review`, `mark_ready`.

## Workflow
1. Use `scan_diff` to inspect the pull request changes.
2. Use `post_review` after the scan.
3. Use `mark_ready` after the review is posted.

You are finished when the review is **posted** and the pull request is **ready for merge**.
