# Cloudflare Workflows

Use Workflows for durable, multi-step jobs that must retry, wait, and resume without losing completed work. An instance is one execution; steps define persistence and retry boundaries.

Fetch the relevant current documentation before implementing. API shapes, configuration, testing helpers, limits, and examples belong in the docs rather than in this reference.

- **Start a project:** [Build your first Workflow]([url-1]) covers scaffolding, configuration, deployment, and a first instance.
- **Design durable execution:** [Rules of Workflows]([url-2]) covers step boundaries, replay, state, and idempotency.
- **Implement or manage an instance:** [Workers API]([url-3]) covers steps, instance operations, parameters, and return types.
- **Check capacity and cost:** fetch [limits]([url-4]) and [pricing]([url-5]) for the target plan.

## In This Reference

- [configuration.md](./configuration.md) — setup, bindings, retry configuration, and local development
- [api.md](./api.md) — steps, instance lifecycle, events, CLI, and REST operations
- [patterns.md](./patterns.md) — design decisions, examples, orchestration, and tests
- [gotchas.md](./gotchas.md) — failures, timeouts, replay, and capacity investigation

## See Also

- [Durable Objects]([url-6]) — stateful coordination
- [Queues](../queues/README.md) — asynchronous message delivery
- [Workers]([url-7]) — application entry points that trigger instances
