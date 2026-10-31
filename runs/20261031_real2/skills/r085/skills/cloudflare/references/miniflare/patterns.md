# Miniflare Testing Patterns

Choose the test runtime before adapting an example. With direct Miniflare, the Worker runs in workerd while the test runner runs in Node.js; importing Worker functions into Node.js can change runtime-dependent behavior. See [writing tests]([url-1]).

| Task | Documentation |
|------|---------------|
| Write unit tests in the Workers runtime | [Workers Vitest setup]([url-2]) |
| Use event, Durable Object, or other runtime test helpers | [Vitest test APIs]([url-3]) |
| Test built Workers from an external runner | [Integration test harness]([url-4]) |
| Build a custom runner with direct simulator control | [Miniflare writing tests]([url-1]) |
| Access emulated bindings from Node.js | [getPlatformProxy]([url-5]) |
| Mock outbound requests in Workers Vitest tests | [Mock outbound requests]([url-6]) |
| Understand Vitest runtime isolation and concurrency | [Isolation and concurrency]([url-7]) |
| Simulate inter-Worker calls and substitute services | [Multiple Workers]([url-8]) |
| Test WebSockets or access local storage | [API routing](./api.md) |

`getPlatformProxy` is for Node.js callers. The Workers Vitest runtime modules require tests running in the Workers runtime; they are not a substitute for calling `getPlatformProxy` in a Node.js test.

For direct Miniflare, clean up instances after tests using the documented [lifecycle]([url-9]). Choose persistence deliberately so tests do not inherit unintended state.
