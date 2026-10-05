---
name: build-duration-budget
description: Run a CI build and capture metrics within the target duration.
allowed-tools: [queue_build, collect_metrics]
---

# Build duration budget

Use this procedure for a CI build that should complete within 15 minutes and then have metrics captured.

Tools: `queue_build`, `collect_metrics`.

## Workflow
1. Use `queue_build` to run the build with a 15 minute target.
2. Use `collect_metrics` after the build completes.

You are finished when metrics are **collected** and the build duration is **within 15 minutes**.
