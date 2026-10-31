# Tail Workers Processing Decisions

Define the destination contract and required event coverage before writing transformations.

| Task | Documentation |
| --- | --- |
| Export supported telemetry without a custom consumer | [OpenTelemetry export]([url-1]) |
| Process and forward custom execution events | [Tail Workers]([url-2]) |
| Aggregate metrics rather than retain individual events | [Analytics Engine from Tail Workers]([url-3]) |
| Choose filters based on execution and request fields | [Tail handler]([url-4]) |
| Review sensitive request data handling | [TailRequest]([url-5]) |

Decide which producers, routes, failures, and successful requests each destination needs. If sampling is appropriate, specify how it affects the questions the data must answer. Minimize retained fields, test transformation and serialization against representative events, and check destination rejection behavior.

Keep producer identity when combining events from multiple Workers. Define how delivery failures become visible before adding fallback storage or batching infrastructure. See [configuration.md](./configuration.md) for deployment ownership.
