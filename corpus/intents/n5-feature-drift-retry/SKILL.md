---
name: feature-drift-retry
description: Feature drift retry procedure.
allowed-tools: [profile_feature_drift, register_drift_report]
---
# Feature drift retry

Use this procedure to prepare a feature drift report for model monitoring.

Tools: `profile_feature_drift`, `register_drift_report`.

## Workflow
1. Run `profile_feature_drift`.
2. Choose repeat or ready.
3. For repeat, return to the profiling step.
4. For ready, proceed after the loop and run `register_drift_report`.

You are finished when the drift report is **registered**.
