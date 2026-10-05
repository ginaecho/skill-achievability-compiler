---
name: lead-scoring-handoff
description: Score campaign leads and create a handoff.
allowed-tools: [import_leads, score_leads, sync_crm, create_handoff]
---

# Lead scoring handoff

Use this procedure for a marketer preparing campaign leads for sales follow-up.

Tools: `import_leads`, `score_leads`, `sync_crm`, `create_handoff`.

## Workflow
1. Use `import_leads` to load the lead list.
2. Use `score_leads` to score the leads.
3. Use `sync_crm` to sync scored leads to the CRM.
4. Use `create_handoff` to create the sales handoff.

You are finished when the CRM is **synced** and the handoff is **created**.
