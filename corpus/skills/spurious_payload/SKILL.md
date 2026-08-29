---
name: book-cheap-flight
description: Book a flight under a 500 budget cap and confirm it by email. Use this when a customer gives a hard price ceiling for their travel.
---

# Book a flight under $500

Your job is finished when a flight is **booked** at a price below 500 and a
**confirmation has been sent**.

## Tools

Tools: search, filter_cheap, book, email.

- `search` marks the route **searched**.
- `filter_cheap` requires the route **searched** and marks the shortlist
  **filtered**. It keeps only fares under 500.
- `book` requires the shortlist **filtered** and marks the flight **booked**.
- `email` requires the flight **booked** and records that the **confirmation
  has been sent**.

## Workflow

1. Search for flights on the requested route.
2. Run the results through `filter_cheap` to drop anything at or above 500.
3. Book one of the remaining fares.
4. Send the confirmation email.

Because step 2 has already removed every fare at or above 500, the reservation
made in step 3 always satisfies the customer's ceiling.
