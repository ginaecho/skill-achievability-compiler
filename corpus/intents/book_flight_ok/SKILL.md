---
name: flight-booking-confirmation
description: Book a customer flight and send its confirmation.
allowed-tools: [search, filter, book, email]
---

# Flight booking confirmation

Use this procedure to turn a flight request into a booked itinerary with a customer confirmation.

Tools: search, filter, book, email.

## Workflow
1. Use `search` to find candidate flights for the request.
2. Use `filter` to narrow the search results to the fares that match the trip details.
3. Use `book` to reserve the selected fare.
4. Use `email` to send the booking confirmation to the customer.

You are finished when the flight is **booked** and the confirmation is **sent**.
