---
name: propensity-model-registry
description: Propensity model registry procedure.
allowed-tools: [prepare_propensity_dataset, train_propensity_model, evaluate_propensity_model, register_propensity_model]
---
# Propensity model registry

Use this procedure to ready a propensity model for reuse by campaigns.

Tools: `prepare_propensity_dataset`, `train_propensity_model`, `evaluate_propensity_model`, `register_propensity_model`.

## Workflow
1. Run `prepare_propensity_dataset`.
2. Run `train_propensity_model` on the prepared data.
3. Run `evaluate_propensity_model` after training.
4. Run `register_propensity_model` after evaluation.

You are finished when the propensity model is **registered**.
