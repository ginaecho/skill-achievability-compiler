---
name: fix-failing-test
description: Find the failing test in this repository, fix the code and confirm the suite passes.
---

# Fix a failing test

Your job is finished when the fix is **verified**.

## Tools

Tools: grep, view, edit, bash.

- `grep` marks the failure **located**.
- `view` requires the failure **located** and marks the code **understood**.
- `edit` requires the code **understood** and marks the fix **applied**.
- `bash` requires the fix **applied** and marks the fix **verified**.

## Workflow

1. Find the failing test with grep.
2. Read the code under test with view.
3. Fix the code with edit.
4. Run the test suite with bash.
