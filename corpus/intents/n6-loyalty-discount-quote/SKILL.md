---
name: loyalty-discount-quote
description: Create and send a loyalty discount quote in CRM.
allowed-tools: [find_profile, create_discount_quote, send_quote]
---

# Loyalty discount quote

Use this procedure when a loyalty customer needs a CRM quote with a discount from 10 to 20 percent.

Tools: `find_profile`, `create_discount_quote`, `send_quote`.

## Workflow
1. Use `find_profile` to open the customer's CRM profile.
2. Use `create_discount_quote` to create a quote with a discount from 10 to 20 percent.
3. Use `send_quote` to send the quote to the customer.

You are finished when the quote is **sent** and the discount is **between 10 and 20 percent**.
