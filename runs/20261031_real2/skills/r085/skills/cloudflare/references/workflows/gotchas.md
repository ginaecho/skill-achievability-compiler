# Gotchas & Debugging

Start with the failing instance and step, then fetch the relevant guide before changing code or resource limits.

| Symptom or question | What to check |
| --- | --- |
| Step timeout or repeated failure | [Sleeping and retrying]([url-1]) for per-attempt timeout, retry policy, and non-retryable failures |
| CPU exhaustion despite a short run | [Limits]([url-2]) for active CPU budgets; increasing an elapsed-time timeout does not increase CPU capacity |
| Missing event or event timeout | [Events and parameters]([url-3]) for instance targeting, event type/payload requirements, and timeout handling |
| State disappears or branches change after resuming | [Rules of Workflows]([url-4]) for persisted step returns, deterministic names and conditionals, and awaited operations |
| Duplicate charge, write, or notification | Review the destination's idempotency guarantees and [step design](./patterns.md#design-decisions); retries can repeat an external operation even when its previous attempt committed |
| Instance ID collision or unexpected batch result | [Workers API]([url-5]) for creation semantics, plus [limits]([url-2]) for retention |
| Oversized results, queued instances, or missing historical data | [Limits]([url-2]) for return/event sizes, concurrency, creation rates, and retention; export required long-term results before expiry |
| Local-only failure or failing introspection test | [Local development]([url-6]) and [Workflow test APIs]([url-7]) |
| Inspect execution and cost | [Metrics and analytics]([url-8]), [Wrangler commands]([url-9]), and [pricing]([url-10]) |

CPU time measures active computation; waiting for network or storage I/O is elapsed time. Event waits, sleeps, and retry delays also have their own documented behavior. Check the current limits page for how these states affect concurrency and step accounting rather than treating every wait as active execution.

See [README.md](./README.md), [configuration.md](./configuration.md), [api.md](./api.md), and [patterns.md](./patterns.md).
