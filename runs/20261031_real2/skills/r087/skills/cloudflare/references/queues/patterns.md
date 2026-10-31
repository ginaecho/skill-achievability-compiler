# Queues Patterns & Best Practices

Fetch the guide matching the task and adapt its example to the application's delivery and failure requirements.

| Task | Documentation |
|------|---------------|
| Accept requests and enqueue asynchronous tasks; publish to multiple queues | [Publish to a Queue via Workers]([url-1]) |
| Buffer writes to an external API or defer a job | [Batching, retries, and delays]([url-2]) |
| Handle upstream rate limits and backpressure | [Handle rate limits of external APIs]([url-3]) and [consumer concurrency]([url-4]) |
| Isolate workloads with different latency or capacity needs | [Configure Queues]([url-5]) |
| Retain exhausted retries for inspection and recovery | [Dead Letter Queues]([url-6]) |
| Process R2 object events | [R2 event notifications]([url-7]) |
| Batch output into R2 | [Use Queues to store data in R2]([url-8]) |
| Batch writes into D1 | [D1 database API]([url-9]) |
| Start durable multi-step jobs | [Trigger Workflows]([url-10]) |
| Publish from a Durable Object | [Use Queues from Durable Objects]([url-11]) |
| Route consumer work to a Durable Object | [Invoke Durable Object methods]([url-12]) |

Design side effects for [at-least-once delivery]([url-13]). A separate check-then-write deduplication flag is not an atomic guarantee: concurrent delivery or a crash between the side effect and recording completion can repeat work. Prefer idempotency keys or transactional enforcement at the destination.

Acknowledge after the destination confirms success. For fan-out, plan for some sends succeeding before another fails; retries must not duplicate downstream effects. Separate queues can isolate workloads, but do not imply a global priority or ordering guarantee.
