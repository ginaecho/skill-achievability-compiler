---
name: vendor-payout-release
description: Release a vendor payout and send remittance.
allowed-tools: [validate_payee_record, process_vendor_payout, send_vendor_remittance]
---

# Vendor payout release

Use this procedure for a payments specialist handling a vendor payout.

Tools: validate_payee_record, process_vendor_payout, send_vendor_remittance.

## Workflow
1. Use `validate_payee_record` to validate the payee record.
2. Use `process_vendor_payout` to release the vendor payout.
3. Use `send_vendor_remittance` to send remittance to the vendor.

You are finished when the payout is **released** and vendor remittance is **sent**.
