---
name: itinerary-routing
description: Route a travel itinerary through the selected reservation path.
allowed-tools: [reserve_window, reserve_direct]
---
# Route an itinerary booking

Use this procedure when a planner selects how a booking desk should reserve a trip.

Tools: `reserve_window`, `reserve_direct`.

Two participants take part: a **planner** and a **booking_desk**.

## Workflow
1. The planner chooses the flexible branch or the fixed branch.
2. For the flexible branch, the planner sends `use_window` to the booking_desk, then the booking_desk runs `reserve_window`.
3. For the fixed branch, the planner sends `use_direct` to the booking_desk, then the booking_desk runs `reserve_direct`.

You are finished when the itinerary is **confirmed**.
