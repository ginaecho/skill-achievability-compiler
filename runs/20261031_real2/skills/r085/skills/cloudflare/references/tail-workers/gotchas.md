# Tail Workers Troubleshooting

Trace one known producer invocation through consumer execution and destination receipt to locate the failure.

| Task | Documentation |
| --- | --- |
| Consumer receives no events or producer setup fails | [Configure Tail Workers]([url-1]) |
| Async processing or event interpretation is incorrect | [Tail handler]([url-2]) |
| Filters confuse HTTP responses with execution failures | [TailItems]([url-3]) |
| Request data is missing or unexpectedly retained | [TailRequest]([url-4]) |
| Inspect producer and consumer execution | [Real-time logs]([url-5]) |
| Reconsider a custom exporter at higher volume | [OpenTelemetry export]([url-6]) |

Verify producer configuration, consumer identity, and destination credentials independently. Include both handled error responses and thrown exceptions when checking filters. Make destination failures observable without exposing the payload or credentials in diagnostic logs. Do not infer retention, retries, or batch guarantees from an example.

See [api.md](./api.md) for data contracts and [patterns.md](./patterns.md) for destination decisions.
