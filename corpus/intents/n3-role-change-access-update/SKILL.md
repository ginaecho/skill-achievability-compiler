---
name: role-change-access-update
description: Role change access update procedure.
allowed-tools: [update_directory_group, open_access_ticket]
---
# Role change access update

Tools: `update_directory_group`, `open_access_ticket`.

## Workflow
1. Two participants take part: an **hr_partner** and an **iam_admin**.
2. The hr_partner sends `role_change_ready` to the iam_admin.
3. The iam_admin runs `update_directory_group`.
4. The iam_admin runs `open_access_ticket` after the group update.

You are finished when the requested role change access update task is **complete**.
