---
name: order-gift-card-reissue
description: Reissue a gift card for an order and email the receipt.
allowed-tools: [find_order, verify_payment, issue_gift_card, email_receipt]
---

# Order gift card reissue

Use this procedure when a shopper needs a gift card reissued for a paid order.

Tools: `find_order`, `verify_payment`, `issue_gift_card`, `email_receipt`.

## Workflow
1. Use `find_order` to locate the order.
2. Use `verify_payment` to confirm the paid order.
3. Use `issue_gift_card` to reissue the gift card.
4. Use `email_receipt` to send the receipt.

You are finished when the gift card is **issued** and the receipt is **emailed**.
