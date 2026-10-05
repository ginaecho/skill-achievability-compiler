---
name: freight-pickup-chain
description: Open, rate, and schedule a freight collection.
allowed-tools: [open_shipment, rate_shipment, schedule_collection]
---
# Arrange freight collection

Use this procedure when a freight_coordinator prepares a shipment for pickup.

Tools: `open_shipment`, `rate_shipment`, `schedule_collection`.

## Workflow
1. Run `open_shipment` for the freight order.
2. Run `rate_shipment` for that shipment.
3. Run `schedule_collection` for carrier collection.

You are finished when the shipment is **rated** and collection is **scheduled**.
