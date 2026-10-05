---
name: budget-fare-confirmation
description: Book a fare below the customer budget and send confirmation.
allowed-tools: [search, book_fare, email]
---

# Budget fare confirmation

Use this procedure when a customer wants a flight fare below 500 with a confirmation message.

Tools: search, book_fare, email.

## Workflow
1. Use `search` to find available fares for the requested trip.
2. Use `book_fare` to book a fare below 500.
3. Use `email` to send the booking confirmation to the customer.

You are finished when a fare below 500 is **booked** and the confirmation is **sent**.
