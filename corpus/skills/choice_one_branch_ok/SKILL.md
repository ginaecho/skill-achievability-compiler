---
name: pay-invoice
description: Pay an invoice by card or by bank transfer. Use this when an invoice must be settled and either payment rail is acceptable.
---

# Pay invoice by card or transfer

Two participants take part: the billing **system** (`sys`) and the **payer**.

Your job is finished when the **invoice is paid**.

## Tools

Tools: pay_card, pay_transfer.

## Workflow

1. The system decides which of two payment rails to use:
   - **card rail** — the system tells the payer `use_card`, and the payer
     settles the invoice with `pay_card`.
   - **transfer rail** — the system tells the payer `use_transfer`, and the
     payer settles the invoice with `pay_transfer`.

Either branch reaches the goal — the invoice ends up paid either way. What
matters is that the payer is always told which rail was chosen, so it never
has to guess.
