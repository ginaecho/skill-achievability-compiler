# Observability Configuration

Fetch the relevant guide before configuring the selected Worker and deployment environment.

| Task | Maintained documentation |
| --- | --- |
| Enable persisted logs, structured JSON logging, and sampling | [Workers Logs]([url-1]) |
| Enable traces and set their sampling independently of logs | [Workers Traces]([url-2]) |
| Configure a named deployment environment | [Wrangler environments]([url-3]) and the environment example in [Workers Logs]([url-1]) |
| Bind an Analytics Engine dataset and write its first data point | [Analytics Engine get started]([url-4]) |
| Connect a producer to a Tail Worker | [Configure Tail Workers]([url-5]) |
| Create a Logpush job, configure access, and enable Worker log delivery | [Workers Logpush]([url-6]) |
| Configure OTLP destinations, authentication, and local persistence | [OpenTelemetry export]([url-7]) for destinations and authentication, and [Workers OpenTelemetry export]([url-8]) for Wrangler destinations and `persist` |

## Setup decisions

- Confirm which account, Worker, and environment will emit telemetry, then deploy that configuration and generate representative traffic.
- Decide log and trace sampling separately. Increasing sampling during an investigation changes volume and cost; restore the intended operational settings afterwards.
- For Tail Workers, configure the consumer relationship on the producer Worker; use the guide for deployment order and the handler contract.
- Choose whether to persist data in Cloudflare as well as exporting it. Verify destination names, supported signal types, and credentials using the export guides above.
- Use stable structured fields and redact secrets and unnecessary personal data before emission. Configure development and production collection intentionally.

See [gotchas.md](gotchas.md) when configured telemetry is missing.
