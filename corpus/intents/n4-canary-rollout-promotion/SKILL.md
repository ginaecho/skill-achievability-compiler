---
name: canary-rollout-promotion
description: Promote a release through a canary check.
allowed-tools: [deploy_canary, run_probe, promote_release]
---

# Canary rollout promotion

Use this procedure to move a service release from canary to promoted state.

Tools: `deploy_canary`, `run_probe`, `promote_release`.

## Workflow
1. Use `deploy_canary` for the canary deployment.
2. Use `run_probe` once the canary is live.
3. Use `promote_release` after the probe is green.

You are finished when the release is **live**.
