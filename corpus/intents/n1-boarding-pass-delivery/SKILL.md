---
name: boarding-pass-delivery
description: Find a flight, select a seat, and send the boarding pass.
allowed-tools: [find_flight, select_seat, send_pass]
---
# Deliver a boarding pass

Use this procedure for a travel_agent preparing a passenger for departure.

Tools: `find_flight`, `select_seat`, `send_pass`.

## Workflow
1. Run `find_flight` for the passenger's trip.
2. Run `select_seat` for the located flight.
3. Run `send_pass` for the selected seat.

You are finished when the seat is **selected** and the boarding pass is **sent**.
