---
name: offboarding-access-closure
description: Offboarding access closure procedure.
allowed-tools: [revoke_directory_access, archive_employee_mailbox, register_asset_return]
---
# Offboarding access closure

Tools: `revoke_directory_access`, `archive_employee_mailbox`, `register_asset_return`.

## Workflow
1. Run `revoke_directory_access` for the employee.
2. Run `archive_employee_mailbox` after access is revoked.
3. Run `register_asset_return` after the mailbox is archived.

You are finished when the requested offboarding access closure task is **complete**.
