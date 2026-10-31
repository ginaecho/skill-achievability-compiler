# Pages Functions Troubleshooting

Start with the request path, deployment environment, and generated output that actually handled the request.

| Task | Documentation |
| --- | --- |
| A Function does not run or receives unexpected parameters | [Routing]([url-1]) |
| Middleware is skipped or static fallback fails | [Advanced mode]([url-2]) |
| Middleware order or scope is incorrect | [Middleware]([url-3]) |
| Bindings or secrets differ between environments | [Bindings]([url-4]) |
| Runtime or environment types do not match | [TypeScript]([url-5]) |
| A local request behaves differently | [Local development]([url-6]) |
| Inspect exceptions and deployment logs | [Debugging and logging]([url-7]) |
| Check runtime quotas | [Workers limits]([url-8]) |
| Check request costs | [Functions pricing]([url-9]) |

Reproduce a failing path through the actual application rather than only calling a handler with a hand-built context. Check the deployed configuration and generated output before changing application code. See [Pages troubleshooting](../pages/gotchas.md) for build, asset, and framework issues.
