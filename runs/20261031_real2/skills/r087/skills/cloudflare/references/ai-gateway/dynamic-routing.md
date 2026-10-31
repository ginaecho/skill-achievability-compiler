# AI Gateway Dynamic Routing

Use a dynamic route when model selection, traffic splitting, quotas, or fallbacks should be controlled in the gateway. For a simple retry or fallback sequence, check the request-handling and fallback guides before introducing a routing flow.

| Task | Current documentation |
|------|-----------------------|
| Design conditional routes, A/B splits, quotas, model fallbacks, and version rollbacks | [Dynamic routing]([url-1]) |
| Invoke a route from an SDK, HTTP request, or Worker; inspect route response metadata | [Using a dynamic route]([url-2]) |
| Define route elements and connections programmatically | [JSON configuration]([url-3]) |
| Provide metadata used by routing conditions | [Custom metadata]([url-4]) |
| Configure model/provider fallbacks | [Fallbacks]([url-5]) |
| Configure retries, backoff, and timeouts | [Request handling]([url-6]) |
| Inspect request outcomes, costs, and errors | [Analytics]([url-7]) and [logging]([url-8]) |

Check the usage guide's authentication and stored-key prerequisites. Dynamic routes still use the [Unified API compatibility endpoint]([url-9]); its single-model deprecation does not make the REST inference endpoint a replacement for route invocation.
