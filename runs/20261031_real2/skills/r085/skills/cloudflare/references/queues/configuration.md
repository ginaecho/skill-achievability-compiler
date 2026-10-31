# Queues Configuration

Fetch the relevant guide before writing configuration or running CLI commands. Check the project's Wrangler version and compatibility date when adapting examples.

| Task | Documentation |
|------|---------------|
| Create a queue and connect producer and consumer Workers | [Getting started]([url-1]) |
| Configure producer bindings, Worker consumers, retention, and concurrency settings | [Configure Queues]([url-2]) |
| Configure an external HTTP consumer and its visibility timeout | [Pull consumers]([url-3]) |
| Choose batching, retry policy, or delivery delays | [Batching, retries, and delays]([url-4]) |
| Preserve messages that exhaust retries | [Dead Letter Queues]([url-5]) |
| Set consumer scaling for downstream capacity | [Consumer concurrency]([url-6]) |
| Choose content types and type Worker messages | [JavaScript APIs]([url-7]) |
| Create, update, attach, remove, or delete queues and consumers | [Wrangler commands]([url-8]) |
| Pause delivery, resume it, or purge messages | [Pause and purge]([url-9]) |
| Develop and test producers and consumers locally | [Local development]([url-10]) |

Choose push or pull based on where processing runs, then select an encoding supported by that consumer. Tune batching for acceptable latency and downstream write capacity. Decide how failed messages will be inspected and replayed before configuring a dead-letter queue.

Fetch [limits]([url-11]) and [pricing]([url-12]) for the account's plan before selecting retention, delays, or capacity. Do not reuse numeric settings from unrelated examples.
