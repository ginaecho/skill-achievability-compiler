---
name: requisition-purchase-order
description: Convert an approved requisition into a supplier order.
allowed-tools: [intake_requisition, approve_budget_check, create_purchase_order, send_supplier_order]
---

# Requisition purchase order

Use this procedure for a buyer processing a requisition.

Tools: intake_requisition, approve_budget_check, create_purchase_order, send_supplier_order.

## Workflow
1. Use `intake_requisition` to intake the requisition.
2. Use `approve_budget_check` to approve the budget check.
3. Use `create_purchase_order` to create the purchase order.
4. Use `send_supplier_order` to send the supplier order.

You are finished when the purchase order is **created** and the supplier order is **sent**.
