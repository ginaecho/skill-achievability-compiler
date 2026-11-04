---
name: two-person-release
description: Release the current build following the skill; the release must be recorded by the tool in
---
# Two Person Release

Your job is finished when the build is **released**.

## Tools

Tools: approve_dev, release.

`release` requires the build to be **countersigned** before it will run.

Each tool is a script: `python tools/<tool>.py`.

## Workflow

1. Get the developer approval with `approve_dev`.
2. Release it with `release`.
