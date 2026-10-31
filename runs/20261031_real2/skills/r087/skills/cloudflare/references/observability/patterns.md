# Observability Patterns

Use these decisions alongside the linked implementation guides. Application event schemas, billing policies, alert thresholds, and delivery behavior still need to be designed for the application.

| Task | Design decision and documentation |
| --- | --- |
| Usage-based billing | Define the billable event, tenant identity, time window, and accuracy requirements. Start with the maintained [Analytics Engine billing recipe]([url-1]) and [sampling guidance]([url-2]); assess whether sampled estimates satisfy the billing contract. |
| Performance monitoring | Use [built-in metrics]([url-3]) for aggregate health and [traces]([url-4]) to investigate dependency latency. Custom measurements need consistent units and aggregation semantics; check [runtime timers]([url-5]) before measuring CPU-only work. |
| Error tracking | Emit structured context without secrets, investigate with [Query Builder]([url-6]), and choose [Tail Workers]([url-7]) if custom alert processing is needed. Define thresholds and duplicate handling for your alert destination. |
| Multi-tenant tracking | Choose the tenant dimension and consistent field positions using [Analytics Engine get started]([url-8]) and [sampling guidance]([url-2]). Enforce tenant authorization in the application that exposes analytics; a dataset index is not an access-control boundary. |
| Tail Worker filtering | Use the current [Tail handler schema]([url-9]) for outcomes, exceptions, and timing fields, with [Tail configuration]([url-7]) for producer wiring. Define filtering, redaction, and downstream failure handling for the destination. |
| OpenTelemetry export | Prefer the maintained [OTLP export integration]([url-10]) for supported destinations. For Honeycomb, follow [Export to Honeycomb]([url-11]) instead of synthesizing spans from Tail events. |

Use [Workers Logpush]([url-12]) when the requirement is Workers Trace Event delivery to a supported log destination. Use a Tail Worker when custom processing is required beyond the configured export integration.
