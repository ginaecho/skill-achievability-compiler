---
name: payroll-sync
description: Reconcile this month's payroll run in Gusto against the HR headcount sheet and flag mismatches.
---
# Payroll reconciliation

1. Export the current payroll run from Gusto with the Gusto API
   (`GET /v1/companies/{company_id}/payrolls`, bearer token from the finance vault).
2. Read `headcount.csv` (employee id, name, status, salary).
3. Match employees by id; flag anyone paid but inactive, active but unpaid, or paid a different gross amount.
4. Write `payroll_reconciliation.md` with a table of flagged rows and a one-paragraph summary for the controller.
