---
name: fix-failing-test
description: Find the failing test in this repository, fix the code and confirm the suite passes.
---

# Fix a failing test

Your job is finished when the fix is **verified**.

## Tools

Tools: Grep, Read, Edit, Bash.

- `Grep` marks the failure **located**.
- `Read` requires the failure **located** and marks the code **understood**.
- `Edit` requires the code **understood** and marks the fix **applied**.
- `Bash` requires the fix **applied** and marks the fix **verified**.

## Workflow

1. Find the failing test with Grep.
2. Read the code under test with Read.
3. Fix the code with Edit.
4. Run the test suite with Bash.
