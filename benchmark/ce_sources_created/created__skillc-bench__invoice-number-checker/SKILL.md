---
name: invoice-number-checker
description: Find gaps and duplicates in a year of invoice numbers before the audit, using a small awk check.
---
# Invoice sequence check

1. Put the invoice export in `invoices.csv` (invoice_no in column 1, sorted or not).
2. Run:
   `cut -d, -f1 invoices.csv | tail -n +2 | sort -n | awk 'NR>1 && $1==p {print "duplicate", $1} NR>1 && $1>p+1 {print "gap", p+1, "to", $1-1} {p=$1}'`
3. Save the output as `sequence_findings.txt` and summarize the number of gaps and duplicates for the auditor.
