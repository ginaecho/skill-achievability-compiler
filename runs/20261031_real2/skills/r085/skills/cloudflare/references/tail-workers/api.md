# Tail Workers APIs

Fetch the handler reference for current event shapes and language examples instead of maintaining local interface definitions.

| Task | Documentation |
| --- | --- |
| Implement the handler and understand asynchronous processing | [Tail handler syntax]([url-1]) |
| Interpret execution outcomes, logs, exceptions, and timestamps | [Tail handler event reference]([url-2]) |
| Inspect request fields and redaction behavior | [TailRequest]([url-3]) |
| Interpret events from dynamic dispatch and user Workers | [Handler parameters]([url-4]) |
| Write aggregated metrics | [Analytics Engine from Tail Workers]([url-5]) |

Choose the event fields required by the destination and preserve the distinction between execution outcome and HTTP response status. Review what data may be retained before bypassing redaction; the documented heuristics are not a complete application privacy policy. See [patterns.md](./patterns.md) for filter design.
