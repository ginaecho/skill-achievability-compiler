---
name: filtered-fare-confirmation
description: Book a filtered fare below budget and send confirmation.
allowed-tools: [search, filter_fares, book, email]
---

# Filtered fare confirmation

Use this procedure when a customer wants a fare below 500, booked and confirmed.

Tools: search, filter_fares, book, email.

## Workflow
1. Use `search` to gather fares for the requested trip.
2. Use `filter_fares` to narrow the fares to choices below 500.
3. Use `book` to reserve the selected fare.
4. Use `email` to send the customer confirmation.

You are finished when a fare below 500 is **booked** and the confirmation is **sent**.
