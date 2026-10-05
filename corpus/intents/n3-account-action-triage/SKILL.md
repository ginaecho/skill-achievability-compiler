---
name: account-action-triage
description: Account action triage procedure.
allowed-tools: [disable_account_now, schedule_access_review]
---
# Account action triage

Tools: `disable_account_now`, `schedule_access_review`.

## Workflow
1. Two participants take part: a **security_coordinator** and an **iam_admin**.
2. The security_coordinator chooses urgent or review.
3. For urgent, the iam_admin runs `disable_account_now`.
4. For review, the iam_admin runs `schedule_access_review`.

You are finished when the requested account action triage task is **complete**.
