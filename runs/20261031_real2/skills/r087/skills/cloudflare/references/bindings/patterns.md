# Binding Patterns

Choose the interaction and lifecycle first, then retrieve the implementation guide.

| Task | Current documentation |
| --- | --- |
| Choose HTTP forwarding or RPC between Workers | [Service bindings]([url-1]) |
| Forward Requests and Responses through a service binding | [Service bindings over HTTP]([url-2]) |
| Expose callable methods with `WorkerEntrypoint` | [Service bindings over RPC]([url-3]) and [RPC TypeScript]([url-4]) |
| Run connected Workers during development | [Developing with multiple Workers]([url-5]) |
| Test handlers against configured bindings and mock dependencies | [Workers Vitest configuration]([url-6]) and [test APIs]([url-7]) |
| Select KV, D1, R2, or Durable Objects | [Storage options]([url-8]) |
| Keep clients current when bindings change | [Binding lifecycle]([url-9]) |
| Manage credentials used by external API clients | [Secrets]([url-10]) |

Use service bindings for internal Worker calls when appropriate, and choose HTTP or RPC based on the interface being exposed. A service binding does not replace application-level authorization for the caller's requested operation.

Choose storage based on access patterns and consistency requirements, not copied size or latency thresholds. Parallelize independent binding operations when useful; preserve ordering where one operation depends on another's result.

Avoid retaining clients derived from mutable bindings across requests without accounting for binding updates. Importing `env` is supported, but binding I/O still requires an appropriate execution context; follow the lifecycle guide rather than assuming all global access is forbidden.
