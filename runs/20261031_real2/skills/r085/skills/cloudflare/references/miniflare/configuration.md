# Miniflare Configuration

Direct Miniflare does not read Wrangler configuration. Configure its bindings explicitly and build TypeScript or bundled Workers before starting tests; see [writing tests]([url-1]).

Match the Worker's intended compatibility date and flags when testing its behavior. Consult [compatibility dates]([url-2]) rather than substituting a fixed date from a sample.

| Configure | Documentation |
|-----------|---------------|
| Script source, HTTP server, request metadata, or reloading | [Get started]([url-3]) |
| Module format and resolution rules | [Modules]([url-4]) |
| Values and file-backed bindings | [Variables and secrets]([url-5]) |
| Service bindings, shared storage, and several Workers | [Multiple Workers]([url-6]) |
| Storage bindings and documented persistence options | [KV]([url-7]), [R2]([url-8]), [D1]([url-9]), [Durable Objects]([url-10]), [Cache]([url-11]) |
| Queue producers and consumers | [Queues]([url-12]) |

If the task is to run tests from the project's build and Wrangler configuration, consider the [integration test harness]([url-13]) or [Workers Vitest setup]([url-14]).
