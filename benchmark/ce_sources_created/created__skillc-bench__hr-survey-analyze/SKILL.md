---
name: hr-survey-analyze
description: Export the quarterly engagement survey from Qualtrics and compute team-level engagement scores.
---
# Engagement survey analysis

1. Export responses for survey `SV_engagement_q3` with the Qualtrics API (API token in `QUALTRICS_TOKEN`).
2. Compute the engagement index per team (mean of items E1-E6, 1-5 scale), with n and a 95% interval.
3. Suppress teams with fewer than 5 responses.
4. Write `engagement_by_team.csv` and a short `engagement_summary.md`.
