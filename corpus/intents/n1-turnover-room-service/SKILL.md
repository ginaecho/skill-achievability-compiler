---
name: turnover-room-service
description: Assign housekeeping, mark a room clean, and release it.
allowed-tools: [assign_housekeeper, mark_clean, release_room]
---
# Turn over a guest room

Use this procedure when the front desk prepares a room between guests.

Tools: `assign_housekeeper`, `mark_clean`, `release_room`.

## Workflow
1. Run `assign_housekeeper` for the room.
2. Run `mark_clean` after the assignment.
3. Run `release_room` after the clean mark.

You are finished when the housekeeper is **assigned**, the room is **clean**, and the room is **released**.
