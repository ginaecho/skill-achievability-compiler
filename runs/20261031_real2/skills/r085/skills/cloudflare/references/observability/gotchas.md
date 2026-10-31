# Observability Troubleshooting and Constraints

## Missing or incomplete data

| Symptom | Check and authoritative guide |
| --- | --- |
| Logs missing from the dashboard | Confirm the deployed Worker/environment, collection and persistence settings, recent traffic, query time range, and sampling. Follow [Workers Logs]([url-1]) and [Query Builder]([url-2]). |
| Live logs differ from stored logs | Confirm which workflow is being inspected; live streams can sample under load. See [real-time logs]([url-3]). |
| Traces missing or incomplete | Check trace enablement and sampling separately from logs, then consult [tracing setup]([url-4]) and [known limitations]([url-5]). |
| Export destination has no data | Check signal type, destination name, credentials, endpoint compatibility, and provider status using [OpenTelemetry export]([url-6]) and, for a Worker, [Workers OpenTelemetry export]([url-7]). For a Logpush job, use [Workers Logpush]([url-8]). |
| Tail consumer receives no events | Check the producer's consumer configuration and deployment using [Tail Workers]([url-9]). |
| Analytics Engine totals or averages look wrong | Account for sample weights and consistent field meanings using [sampling guidance]([url-10]). Check [limits]([url-11]) for missing writes or expired data. |
| Very short operations appear to take no time | Read [performance and timers]([url-12]) and [trace limitations]([url-5]). Tracing does not eliminate the runtime's timing restrictions. |

## Limits, retention, and cost

Fetch these pages when estimating cost or diagnosing truncation and missing data:

- [Workers Logs]([url-1]): log size, retention, sampling, and pricing.
- [Workers Traces]([url-4]) and [known limitations]([url-5]): availability, propagation, and instrumentation constraints.
- [Workers pricing]([url-13]): current observability and Tail Worker billing terms.
- [Analytics Engine limits]([url-11]) and [pricing]([url-14]): field/write limits, retention, query costs, and billing availability.
- [Workers Logpush]([url-8]): Workers-specific eligibility, permissions, and pricing.

Sampling reduces coverage as well as volume. Do not interpret the absence of a sampled event as proof that an error did not happen. Keep required diagnostic context while avoiding credentials, full sensitive URLs, and unnecessary personal data in logs, custom dimensions, and exported records.
