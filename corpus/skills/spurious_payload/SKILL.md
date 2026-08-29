---
name: book-cheap-flight
description: Book a flight under a 500 budget cap and confirm it by email. Use this when a customer gives a hard price ceiling for their travel.
---

# Book a flight under $500

Your job is finished when a flight is **booked at a price below 500** and a
**confirmation has been sent**.

## Tools

Tools: search, filter_cheap, book, send_email.

`filter_cheap` keeps only fares under 500. Anything it passes through is
already within the customer's budget.

## Workflow

1. Search for flights on the requested route.
2. Run the results through `filter_cheap` to drop anything at or above 500.
3. Book one of the remaining fares.
4. Send the confirmation email.

Because step 2 has already removed every fare at or above 500, the booking in
step 3 always satisfies the customer's price ceiling.
