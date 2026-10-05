---
name: runner-queue-target
description: Start a runner and announce readiness inside the target queue time.
allowed-tools: [start_runner, notify_runner_ready]
---

# Runner queue target

Use this procedure when a CI runner should be ready with a queue wait under 10 minutes.

Tools: `start_runner`, `notify_runner_ready`.

## Workflow
1. Use `start_runner` to start the hosted runner.
2. Use `notify_runner_ready` after the runner has started.

You are finished when the runner ready notice is **sent** and the queue wait is **under 10 minutes**.
