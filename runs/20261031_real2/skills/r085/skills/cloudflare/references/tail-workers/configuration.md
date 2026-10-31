# Tail Workers Configuration

Identify the producer Worker and consumer Worker as separate deployment resources before changing their configuration.

| Task | Documentation |
| --- | --- |
| Connect a producer to a Tail Worker | [Configure Tail Workers]([url-1]) |
| Configure environments and resource bindings | [Wrangler configuration]([url-2]) |
| Configure destination credentials | [Secrets]([url-3]) |
| Use built-in telemetry destinations instead | [OpenTelemetry export]([url-4]) |
| Check availability and billing model | [Tail Workers]([url-5]) |
| Check runtime capacity | [Workers limits]([url-6]) |
| Check the handler required by the consumer | [Tail handler]([url-7]) |

Confirm which project owns each deployment and which environment the destination belongs to. Verify a known producer request reaches the intended destination before expanding coverage. See [api.md](./api.md) for payload handling and [gotchas.md](./gotchas.md) for investigation.
