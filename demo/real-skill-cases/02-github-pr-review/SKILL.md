---
name: github-pr-review-handoff
description: Read an issue, push a branch, open a pull request, and request review.
source: https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent
---

# GitHub pull-request handoff

The goal deliberately stops at a review request. Approval and merge remain a
human-controlled obligation rather than something the agent claims to achieve.

```skillc-pack
{
  "name": "github-pr-review-handoff",
  "roles": ["coding_agent", "reviewer"],
  "capabilities": {
    "read_issue": {
      "owner": "coding_agent",
      "add": ["issue_understood"]
    },
    "push_branch": {
      "owner": "coding_agent",
      "pre": "issue_understood",
      "add": ["branch_pushed"]
    },
    "create_pull_request": {
      "owner": "coding_agent",
      "pre": "branch_pushed",
      "add": ["pr_opened"]
    },
    "request_review": {
      "owner": "coding_agent",
      "pre": "pr_opened",
      "add": ["review_requested"]
    }
  },
  "protocol": [
    {"act": {"cap": "read_issue", "by": "coding_agent"}},
    {"act": {"cap": "push_branch", "by": "coding_agent"}},
    {"act": {"cap": "create_pull_request", "by": "coding_agent"}},
    {"act": {"cap": "request_review", "by": "coding_agent"}},
    {"msg": {"from": "coding_agent", "to": "reviewer", "label": "review_requested"}},
    {"goal": {"and": ["pr_opened", "review_requested"]}}
  ],
  "goal": {"and": ["pr_opened", "review_requested"]}
}
```

