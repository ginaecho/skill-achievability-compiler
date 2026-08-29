---
name: book-flight-and-confirm
description: Book a flight for a customer and send them a confirmation email. Use this when a customer asks to book travel and expects written confirmation.
---

# Book a flight and confirm

Your job is finished when the flight is **booked** and a **confirmation has
been sent** to the customer.

## Tools

Tools: search, filter, book, email.

- `search` marks the route **searched**.
- `filter` requires the route **searched** and marks the shortlist
  **filtered**.
- `book` requires the shortlist **filtered** and marks the flight **booked**.
- `email` requires the flight **booked** and records that the **confirmation
  has been sent**.

## Workflow

1. Search for candidate flights on the requested route and dates.
2. Filter the results down to the ones that match what the customer asked for.
3. Book the chosen flight.
4. Send the customer a confirmation email.

Do not send the confirmation before the reservation has actually gone through —
the message must describe something real.
