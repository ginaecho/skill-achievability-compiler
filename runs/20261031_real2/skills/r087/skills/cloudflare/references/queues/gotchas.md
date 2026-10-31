# Queues Gotchas & Troubleshooting

Fetch the linked documentation before changing retry policy or interpreting delivery behavior.

| Symptom or question | Documentation and decision |
|---------------------|----------------------------|
| Successful work repeats after another message fails | Read [acknowledgement and retry rules]([url-1]); use per-message outcomes for independent work. |
| A caught failure disappears instead of retrying | Read [handler lifecycle and APIs]([url-2]); returning successfully can acknowledge messages. Explicitly retry failed work when continuing. |
| Duplicate processing | Read [delivery guarantees]([url-3]); enforce idempotency at the side-effect destination. |
| Pull consumers cannot decode payloads | Check [pull consumer encoding]([url-4]) and [content types]([url-2]) against the producer. |
| Messages stop arriving or backlog grows | Check [consumer configuration]([url-5]), [pause state]([url-6]), and [queue metrics]([url-7]). |
| Dead-letter volume rises or messages disappear after retries | Read [Dead Letter Queues]([url-8]); inspect failures and plan recovery before increasing retries. |
| API errors, resource exhaustion, or CPU failures | Read [error codes]([url-9]), [limits]([url-10]), and [consumer concurrency]([url-11]). |
| Retention, delay, throughput, or cost assumptions no longer hold | Retrieve current [limits]([url-10]) and [pricing]([url-12]) for the account's plan. |

Distinguish transient dependency failures from invalid payloads before choosing retry or recovery behavior. Acknowledging a failed message does not send it to a dead-letter queue. If handling a permanent failure separately, persist the intended recovery record successfully before acknowledging; use the documented dead-letter policy when relying on retry exhaustion.

See [patterns.md](./patterns.md) for idempotency and downstream integration decisions.
