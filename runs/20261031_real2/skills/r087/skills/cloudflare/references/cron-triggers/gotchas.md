# Cron Triggers Troubleshooting

Investigate using the current documentation rather than copied limits or assumed delivery guarantees.

| Symptom or question | Documentation and check |
| --- | --- |
| Job runs at an unexpected time | Check [UTC execution]([url-1]) and [expression syntax]([url-2]); compare with the intended business timezone. |
| Schedule is missing after deployment | Check the handler, target environment, and propagation guidance in [Add a Cron Trigger]([url-3]). |
| Removing or preserving schedules has an unexpected result | Review [Remove a Cron Trigger]([url-4]) before changing empty or omitted configuration. |
| Local invocation fails | Follow [Test Cron Triggers locally]([url-5]) for the supported endpoint, port, and query parameters. |
| Async work fails or completion status is surprising | Read [handler methods]([url-6]) and inspect [past events]([url-7]). |
| Job exceeds its execution budget | Check [Workers limits]([url-8]) before choosing a smaller unit of work or [Workflows](../workflows/README.md). |
| Green Compute behavior differs from expectations | Read [Green Compute]([url-9]) for its execution-location policy and account configuration. |

For repeated or partially completed business operations, decide how to identify work and recover safely before selecting storage. Test recovery after each side effect; a marker alone does not establish that the operation completed. Do not assume a particular automatic retry schedule or delivery guarantee without a documented contract.

See [patterns.md](./patterns.md) for coordination choices and [api.md](./api.md) for tests.
