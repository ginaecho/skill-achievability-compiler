---
name: book-flight-and-confirm
description: Book a flight for a customer and email them a confirmation. Use this when a customer books travel and expects written confirmation.
---

# Book a flight and confirm

Your job is finished when the flight is **booked** and a **confirmation has
been sent** to the customer.

## Tools

Required tools: search, filter, book, send_email.

- `search` marks the route **searched**.
- `filter` requires the route **searched** and marks the shortlist
  **filtered**.
- `book` requires the shortlist **filtered** and marks the flight **booked**.
- `send_email` requires the flight **booked** and marks **confirmation sent**.

## Workflow

1. Search for candidate flights.
2. Filter down to the ones matching the customer's request.
3. Book the chosen flight.
4. Then write to the customer via `send_email`.
