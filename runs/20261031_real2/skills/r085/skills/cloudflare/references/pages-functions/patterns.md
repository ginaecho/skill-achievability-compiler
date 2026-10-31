# Pages Functions Request Design

Choose where behavior belongs before adapting an example.

| Task | Documentation |
| --- | --- |
| Share authentication, logging, and error handling | [Middleware]([url-1]) |
| Choose request handlers and asynchronous completion behavior | [API reference]([url-2]) |
| Keep asset requests outside Function invocation where appropriate | [Routing]([url-3]) |
| Use custom or framework-generated routing | [Advanced mode]([url-4]) |
| Integrate storage or another service | [Bindings]([url-5]) |
| Exercise the assembled application locally | [Local development]([url-6]) |

Define the response owner and middleware scope before adding authentication or response transformations. Test protected routes, rejected requests, and static fallbacks together. Choose consistency and concurrency requirements before using storage for session state or rate limiting; a generic read-modify-write example is not a complete policy.

See [Pages project decisions](../pages/patterns.md) for framework and migration work.
