# Browser Run Troubleshooting

Identify the integration and observed failure before changing timeouts or concurrency. A request-rate limit, exhausted browser time, and a closed session require different responses.

| Concern | Documentation |
|---------|---------------|
| Quotas, launch rates, concurrency, and session timeouts | [Limits]([url-1]) — check the current plan and integration-specific limits |
| Browser hours and concurrent-browser charges | [Pricing]([url-2]) — distinguish Quick Actions from browser sessions |
| Missing bindings, action failures, or unsupported behavior | [FAQ]([url-3]) — diagnose the reported error and runtime constraints |
| Puppeteer page evaluation cannot access outer variables | [JavaScript execution]([url-4]) — browser execution context, passing arguments, and returned values |
| Block resources or handle intercepted Puppeteer requests | [Request interception]([url-5]) — continue, respond, or abort requests and avoid duplicate handling |
| Unexpected disconnects or session loss | [Browser close reasons]([url-6]) — inspect the recorded close reason before choosing recovery |
| Development or compatibility failures | [Wrangler reference]([url-7]) — verify binding configuration and interface-specific development support |

Before increasing concurrency, check session cleanup and whether the workload can reuse browsers with appropriate isolation; see [patterns.md](patterns.md). Retrieve current limits and pricing when sizing a workload rather than relying on fixed tier tables.
