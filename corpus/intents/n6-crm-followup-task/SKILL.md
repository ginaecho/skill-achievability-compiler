---
name: crm-followup-handoff
description: Update a CRM opportunity and create the follow-up handoff task.
allowed-tools: [update_stage, create_followup_task, log_handoff]
---

# CRM follow-up handoff

Use this procedure when a sales rep is handing a CRM opportunity to an account coordinator. Two participants take part: a **sales_rep** and an **account_coordinator**.

Tools: `update_stage`, `create_followup_task`, `log_handoff`.

## Workflow
1. The **sales_rep** uses `update_stage` on the opportunity.
2. The **sales_rep** sends `stage_ready` to the **account_coordinator**.
3. The **account_coordinator** uses `create_followup_task`.
4. The **sales_rep** uses `log_handoff`.

You are finished when the stage is **updated**, the follow-up task is **created**, and the handoff is **logged**.
