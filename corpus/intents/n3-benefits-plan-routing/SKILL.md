---
name: benefits-plan-routing
description: Benefits enrollment routing procedure.
allowed-tools: [record_standard_enrollment, record_executive_enrollment]
---
# Benefits enrollment routing

Tools: `record_standard_enrollment`, `record_executive_enrollment`.

## Workflow
1. Two participants take part: a **benefits_lead** and an **hr_specialist**.
2. The benefits_lead chooses standard or executive.
3. For standard, send `use_standard_plan` to the hr_specialist, then run `record_standard_enrollment`.
4. For executive, send `use_executive_plan` to the hr_specialist, then run `record_executive_enrollment`.

You are finished when the requested benefits enrollment routing task is **complete**.
