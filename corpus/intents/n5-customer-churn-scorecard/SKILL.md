---
name: customer-churn-scorecard
description: Customer churn scorecard procedure.
allowed-tools: [pull_customer_features, train_churn_classifier, publish_churn_scorecard]
---
# Customer churn scorecard

Use this procedure to prepare customer churn scoring for the retention team.

Tools: `pull_customer_features`, `train_churn_classifier`, `publish_churn_scorecard`.

## Workflow
1. Run `pull_customer_features` to prepare the modeling table.
2. Run `train_churn_classifier` and target an AUC score of at least 80.
3. Run `publish_churn_scorecard` for the business scorecard.

You are finished when the scorecard is **published** and the AUC score is at least **80**.
