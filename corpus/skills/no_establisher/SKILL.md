---
name: book-flight-and-confirm
description: Book a flight for a customer so that the booking is confirmed. Use this when a customer asks to book travel.
---

# Book a flight and confirm

Your job is finished when the flight is **booked** and a **confirmation has
been sent** to the customer.

## Tools

Required tools: search, filter, book, notify_customer.

- `search` marks the route **searched**.
- `filter` requires the route **searched** and marks the shortlist
  **filtered**.
- `book` requires the shortlist **filtered** and marks the flight **booked**.
- `notify_customer` requires the flight **booked** and marks a notification
  **queued**.

## Workflow

1. Search for candidate flights.
2. Filter down to the ones matching the customer's request.
3. Book the chosen flight.
4. Notify the customer.
