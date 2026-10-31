# Cron Triggers Patterns

Choose the execution boundary before writing a scheduled job; fetch the relevant integration docs for implementation.

| Need | Documentation |
| --- | --- |
| Periodic API sync, cleanup, reports, or health checks in a Worker | [Cron Triggers background]([url-1]) and [scheduled handler]([url-2]) |
| Different jobs on different schedules | [Handle multiple cron triggers]([url-3]) |
| Durable multi-step work started on a schedule | [Trigger Workflows]([url-4]) |
| Send work to a queue and implement its consumer | [Queues JavaScript APIs]([url-5]) |
| Coordinate state across invocations | [What are Durable Objects?]([url-6]) |
| Inspect whether scheduled work ran | [View past events]([url-7]) |

Keep the trigger separate from the business operation so manual recovery and scheduled execution can share it. Decide how partial progress is recorded, how repeated attempts affect side effects, and who owns completion reporting. When distributing a batch, distinguish successful enqueueing from successful processing.

Use [Workers limits]([url-8]) to evaluate whether the job fits one invocation. If it needs durable steps, waiting, or explicit retry boundaries, inspect [Workflows](../workflows/README.md) before building those mechanisms in the handler.

See [api.md](./api.md) for tests and [gotchas.md](./gotchas.md) for operational checks.
