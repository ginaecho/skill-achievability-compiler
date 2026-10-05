---
name: cache-backed-test-artifact
description: Run cached tests and save an artifact.
allowed-tools: [restore_cache, run_tests, save_artifact]
---

# Cache backed test artifact

Use this procedure when a CI worker needs to produce a test artifact from a cached setup.

Tools: `restore_cache`, `run_tests`, `save_artifact`.

## Workflow
1. Use `restore_cache` to prepare cached dependencies.
2. Use `run_tests` after the cache is ready.
3. Use `save_artifact` after tests are green.

You are finished when tests are **green** and the artifact is **saved**.
