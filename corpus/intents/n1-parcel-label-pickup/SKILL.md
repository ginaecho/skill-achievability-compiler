---
name: parcel-label-pickup
description: Create a parcel label, book pickup, and send tracking.
allowed-tools: [create_label, book_pickup, send_tracking]
---
# Create parcel label and pickup

Use this procedure when a shipper prepares a parcel for carrier pickup.

Tools: `create_label`, `book_pickup`, `send_tracking`.

## Workflow
1. Run `create_label` for the parcel.
2. Run `book_pickup` for the labelled parcel.
3. Run `send_tracking` after pickup booking.

You are finished when the label is **created**, pickup is **booked**, and tracking is **sent**.
