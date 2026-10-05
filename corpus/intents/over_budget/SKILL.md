---
name: fare-budget-confirmation
description: Book a fare below the customer budget and send confirmation.
allowed-tools: [search, book_fare, email]
---

# Fare budget confirmation

Use this procedure when a customer asks for a flight fare below 500 and a confirmation.

Tools: search, book_fare, email.

## Workflow
1. Use `search` to find fares for the requested trip.
2. Use `book_fare` to book a fare below 500.
3. Use `email` to send the customer confirmation.

You are finished when a fare below 500 is **booked** and the confirmation is **sent**.
