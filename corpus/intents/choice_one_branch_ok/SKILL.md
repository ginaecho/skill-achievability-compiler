---
name: invoice-payment-rail
description: Select a payment rail and complete the invoice payment.
allowed-tools: [pay_card, pay_transfer]
---
# Pay an invoice by selected rail

Use this procedure when a system participant chooses how a payer should pay an invoice.

Tools: `pay_card`, `pay_transfer`.

Two participants take part: a **sys** participant and a **payer**.

## Workflow
1. The sys participant chooses card or transfer.
2. For card, sys sends `use_card` to the payer, then the payer runs `pay_card`.
3. For transfer, sys sends `use_transfer` to the payer, then the payer runs `pay_transfer`.

You are finished when the payment rail is **selected** and the invoice is **paid**.
