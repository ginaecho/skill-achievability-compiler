---
name: book-cheap-flight
description: Book a flight under a 500 budget cap and confirm it by email. Use this when a customer gives a hard price ceiling for their travel.
---

# Book a flight under $500

Your job is finished when a flight is **booked** at a price below 500 and a
**confirmation has been sent**.

## Tools

Tools: search, book_cheap, email.

- `search` marks the route **searched**.
- `book_cheap` requires the route **searched** and marks the flight
  **booked**. It only books fares under 500 — if nothing under that price is
  available it will not book anything.
- `email` requires the flight **booked** and records that the **confirmation
  has been sent**.

## Workflow

1. Search for flights on the requested route.
2. Book with `book_cheap`.
3. Send the confirmation email.

The price constraint is part of the goal, not a preference: a booking at 500
or above does not count as success.
