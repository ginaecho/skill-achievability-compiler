---
name: canary-model-release
description: Canary model release procedure.
allowed-tools: [package_model_artifact, run_canary_evaluation, promote_canary_model]
---
# Canary model release

Use this procedure for an ML operations canary release.

Tools: `package_model_artifact`, `run_canary_evaluation`, `promote_canary_model`.

## Workflow
1. Run `package_model_artifact` for the release candidate.
2. Run `run_canary_evaluation` on the packaged artifact.
3. Run `promote_canary_model` after the canary evaluation.

You are finished when the canary model is **promoted**.
