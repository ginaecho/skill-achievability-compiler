# Cron Triggers Configuration

Fetch the documentation for the configuration operation before changing schedules.

| Task | Documentation |
| --- | --- |
| Add a handler and configure triggers, including per-environment schedules and deployment propagation | [Add a Cron Trigger]([url-1]) |
| Choose an expression, interpret weekday numbering, or check supported extensions | [Supported cron expressions]([url-2]) |
| Remove schedules or distinguish omission from an empty configuration | [Remove a Cron Trigger]([url-3]) |
| Configure renewable-energy execution locations | [Green Compute]([url-4]) |
| Check trigger counts and execution budgets | [Workers limits]([url-5]) |
| Schedule Workflow instances directly | [Schedule a Workflow directly]([url-6]) |

Identify the target environment and the intended business timezone before choosing an expression. Review which schedules a deployment will replace, and use the documented propagation behavior when planning a rollout. For Green Compute, follow its account-level configuration rather than inferring settings from Worker placement.

See [api.md](./api.md) for implementation and [gotchas.md](./gotchas.md) for verification.
