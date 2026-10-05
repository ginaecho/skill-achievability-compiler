---
name: portal-onboarding-message
description: Create a portal account and send onboarding information.
allowed-tools: [create_portal_account, send_welcome_message]
---

# Portal onboarding message

Use this procedure when patient services staff set up portal onboarding.

Tools: `create_portal_account`, `send_welcome_message`.

## Workflow
1. Use `create_portal_account` to create the portal account.
2. Use `send_welcome_message` to send the onboarding message.

You are finished when the account is **account_created** and the welcome message is **welcome_sent**.
