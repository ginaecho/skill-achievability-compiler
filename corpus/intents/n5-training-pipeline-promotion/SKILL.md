---
name: training-pipeline-promotion
description: Training pipeline promotion procedure.
allowed-tools: [train_forecast_pipeline, promote_forecast_pipeline]
---
# Training pipeline promotion

Use this procedure for promoting a forecasting pipeline in ML operations.

Tools: `train_forecast_pipeline`, `promote_forecast_pipeline`.

## Workflow
1. Run `train_forecast_pipeline` for the forecasting pipeline.
2. Run `promote_forecast_pipeline` after training.

You are finished when the forecasting pipeline is **promoted**.
