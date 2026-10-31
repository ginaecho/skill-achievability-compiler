# Stream Configuration

Inspect the existing runtime, API client or binding, authentication layer, player, and secret storage before adding Stream. Choose upload and viewing permissions from the application's requirements.

| Task | Read |
|---|---|
| Configure Stream in a Worker and use its binding | [Stream binding setup]([url-1]) |
| Set creator upload constraints and metadata | [Direct creator uploads]([url-2]) |
| Choose a token endpoint, Worker binding, or signing key | [Token-generation choices]([url-3]) |
| Require private playback or apply token restrictions | [Secure your Stream]([url-4]) |
| Restrict embedding origins | [Allowed origins]([url-5]) |
| Configure processing notifications and their secret | [Video webhooks]([url-6]) |
| Configure live recording or external destinations | [Live inputs]([url-7]) and [simulcasting]([url-8]) |
| Choose player configuration or framework integration | [Stream Player]([url-9]) |

Use the project's server-side secret handling for API tokens, signing keys, and webhook secrets. Identify the authorization check that permits issuing an upload URL or playback token; Stream configuration alone does not define the application's user entitlements.

See [api.md](./api.md), [api-live.md](./api-live.md), and [gotchas.md](./gotchas.md).
