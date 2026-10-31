# Cloudflare Tail Workers

Use Tail Workers when execution events need custom processing. Fetch the current documentation before implementing handlers, configuration, or integrations.

| Task | Documentation |
| --- | --- |
| Decide whether custom processing is needed | [Tail Workers]([url-1]) |
| Export logs and traces to an observability destination | [OpenTelemetry export]([url-2]) |
| Inspect a deployment interactively | [Real-time logs]([url-3]) |
| Implement the consumer | [Tail handler]([url-4]) |

Before adding a Tail Worker, check whether built-in OpenTelemetry export meets the destination’s needs. Use the Tail Workers guide for the tradeoff, then identify the custom filtering or transformation that remains necessary.

## In This Reference

- [configuration.md](./configuration.md) — producer, consumer, destination, and environment setup
- [api.md](./api.md) — event fields, execution outcomes, and redaction
- [patterns.md](./patterns.md) — destination and filtering decisions
- [gotchas.md](./gotchas.md) — connection, data, and delivery investigation

See [observability](../observability/README.md) for broader logging and tracing choices.
