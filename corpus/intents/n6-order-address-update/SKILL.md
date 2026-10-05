---
name: order-address-update
description: Update an order shipping address and record the change.
allowed-tools: [lookup_order, edit_shipping_address, save_order_note]
---

# Order address update

Use this procedure when a shopper asks to change the shipping address on an order.

Tools: `lookup_order`, `edit_shipping_address`, `save_order_note`.

## Workflow
1. Use `lookup_order` to find the order.
2. Use `edit_shipping_address` to update the shipping address.
3. Use `save_order_note` to record the address change.

You are finished when the shipping address is **updated** and the order note is **saved**.
