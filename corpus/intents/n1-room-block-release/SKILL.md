---
name: room-block-release
description: Create a room block and release its group booking link.
allowed-tools: [create_room_block, release_group_link]
---
# Release a group booking link

Use this procedure when a sales_manager prepares a hotel group block.

Tools: `create_room_block`, `release_group_link`.

## Workflow
1. Run `create_room_block` for the group.
2. Run `release_group_link` for the created block.

You are finished when the group booking link is **released**.
