---
name: protected-production-deployment
description: Trigger and monitor a deployment to an environment requiring a distinct human reviewer.
source: https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments
---

# Protected GitHub Actions deployment

The environment requires approval and prevents self-review. The agent can
trigger and inspect the workflow, but no declared capability grants the separate
human approval required by the deployment job.

```skillc-pack
{
  "name": "protected-production-deployment",
  "roles": ["deployment_agent", "required_reviewer"],
  "capabilities": {
    "trigger_workflow": {
      "owner": "deployment_agent",
      "add": ["run_started"]
    },
    "poll_workflow": {
      "owner": "deployment_agent",
      "pre": "run_started",
      "add": ["run_status_known"]
    },
    "deploy_job": {
      "owner": "deployment_agent",
      "pre": {"and": ["run_status_known", "environment_approved"]},
      "add": ["deployed"]
    }
  },
  "protocol": [
    {"act": {"cap": "trigger_workflow", "by": "deployment_agent"}},
    {"act": {"cap": "poll_workflow", "by": "deployment_agent"}},
    {"act": {"cap": "deploy_job", "by": "deployment_agent"}}
  ],
  "goal": "deployed"
}
```

