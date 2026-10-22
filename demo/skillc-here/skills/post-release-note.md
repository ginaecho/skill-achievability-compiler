---
name: post-release-note
description: Summarise the merged pull requests and post the release note to the team Slack channel.
---

# Post a release note

Your job is finished when the release note is **posted**.

## Tools

Tools: Bash, slack_send_message.

- `Bash` marks the changes **collected**.
- `slack_send_message` requires the changes **collected** and marks the release note **posted**.

## Workflow

1. List the merged pull requests with Bash.
2. Post the release note with slack_send_message.
