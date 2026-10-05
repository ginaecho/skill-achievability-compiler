---
name: room-rate-ceiling
description: Reserve a hotel room under a stated nightly ceiling.
allowed-tools: [quote_room, reserve_room, email_guest]
---
# Reserve a room within rate ceiling

Use this procedure for a reservations desk booking a room at or below 200 per night.

Tools: `quote_room`, `reserve_room`, `email_guest`.

## Workflow
1. Run `quote_room` to obtain the room quote.
2. Run `reserve_room` for the quoted room.
3. Run `email_guest` to send the guest details.

You are finished when the room is **reserved**, the guest is **emailed**, and the nightly rate is at or below **200**.
