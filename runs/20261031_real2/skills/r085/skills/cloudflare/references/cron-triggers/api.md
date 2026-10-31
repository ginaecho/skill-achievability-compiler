# Cron Triggers API

Fetch the handler documentation before writing code; use its current language examples and completion semantics.

| Task | Documentation |
| --- | --- |
| Implement the handler and access the cron expression, scheduled time, bindings, and context | [Scheduled handler]([url-1]) |
| Route different schedules to different operations | [Handle multiple cron triggers]([url-2]) |
| Await work and understand how asynchronous failures affect invocation status | [Handler methods]([url-3]) |
| Invoke a scheduled handler locally with a chosen expression or time | [Test Cron Triggers locally]([url-4]) |
| Build tests using runtime-backed controllers and execution contexts | [Workers test APIs]([url-5]) |
| Start and inspect a Workflow instance | [Trigger Workflows]([url-6]) |

Decide which operation establishes successful completion and make its failures observable. Test each configured schedule and partial-failure recovery. Read the local-testing documentation for the current endpoint and query parameters instead of adding a production HTTP route to imitate the development helper.

See [patterns.md](./patterns.md) for execution design and [gotchas.md](./gotchas.md) for failures.
