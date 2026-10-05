---
name: crm-renewal-path
description: Choose a renewal path and start the matching CRM action.
allowed-tools: [send_standard_offer, prepare_save_plan]
---

# CRM renewal path

Use this procedure when an account lead selects the renewal path for an account. Two participants take part: an **account_lead** and a **renewal_specialist**.

Tools: `send_standard_offer`, `prepare_save_plan`.

## Workflow
1. The **account_lead** chooses either the standard path or the save path.
2. On the standard path, the **renewal_specialist** uses `send_standard_offer`.
3. On the save path, the **renewal_specialist** uses `prepare_save_plan`.

You are finished when renewal work is **started**.
