# Containers patterns

Choose instance identity based on the workload: per-user/session or per-job identities for affinity, one shared identity for a singleton, and interchangeable instances for stateless requests. Read [scaling and routing]([url-1]) for current helpers and scaling behavior before implementing that choice.

| Task | Documentation |
| --- | --- |
| Distribute requests across stateless instances | [Stateless instances example]([url-2]) |
| Forward WebSocket connections | [WebSocket example]([url-3]) |
| React to lifecycle changes | [Status hooks example]([url-4]) |
| Handle shutdown and persist data across restarts | [Container lifecycle]([url-5]) and [Container interface]([url-6]) |
| Keep long operations active or schedule callbacks | [Activity renewal]([url-7]) and [scheduling]([url-8]) |
| Start containers on a cron schedule | [Cron container example]([url-9]) |
| Route requests to multiple ports | [Request methods]([url-10]) and [utility functions]([url-11]) |
| Access Workers bindings from the container | [Connect to Workers and bindings]([url-12]) |

## Workflows and Queues

For multi-step orchestration, combine the [Workflows Workers API]([url-13]) with the [Container API](api.md). For queue-driven jobs, read the [Queues consumer API]([url-14]) and [acknowledgement and retry behavior]([url-15]) alongside the Container API. These pages document the component APIs; they are not end-to-end Container integration examples.
