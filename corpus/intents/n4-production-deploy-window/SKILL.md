---
name: production-deploy-window
description: Build a release and deploy it to production.
allowed-tools: [build_release, deploy_production]
---

# Production deploy window

Use this procedure for a release manager deploying a built release to production.

Tools: `build_release`, `deploy_production`.

## Workflow
1. Use `build_release` to build the release artifact.
2. Use `deploy_production` after the release is built.

You are finished when production is **deployed**.
