---
name: book-a-table
description: Ask the user which evening suits them, then book a restaurant table.
---

# Book a table

Your job is finished when the table is **booked**.

## Tools

Tools: ask_user_input_v0, web_search.

- `ask_user_input_v0` marks the evening **chosen**.
- `web_search` requires the evening **chosen** and marks the table **booked**.

## Workflow

1. Ask the user which evening suits them with ask_user_input_v0.
2. Book the table with web_search.
