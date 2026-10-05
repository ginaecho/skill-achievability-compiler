---
name: new-hire-payroll-sync
description: New hire payroll sync procedure.
allowed-tools: [create_onboarding_profile, provision_directory_account, sync_payroll_record]
---
# New hire payroll sync

Tools: `create_onboarding_profile`, `provision_directory_account`, `sync_payroll_record`.

## Workflow
1. Run `create_onboarding_profile` for the new hire.
2. Run `provision_directory_account` after the profile is created.
3. Run `sync_payroll_record` after the directory account is provisioned.

You are finished when the requested new hire payroll sync task is **complete**.
