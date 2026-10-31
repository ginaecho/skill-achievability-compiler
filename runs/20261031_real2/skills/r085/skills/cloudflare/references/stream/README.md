# Cloudflare Stream

Use Stream for on-demand video upload and playback or live broadcasting. Start with the application's upload source, player, and access requirements, then read the corresponding documentation before writing code.

## Choose a Workflow

| Task | Read |
|---|---|
| Let users upload without exposing an API token | [Direct creator uploads]([url-1]) |
| Choose server upload, resumable upload, or import from a URL | [Upload methods and supported formats]([url-2]) |
| Embed playback or integrate an existing player | [Stream Player]([url-3]) or [HLS/DASH players]([url-4]) |
| Restrict viewing to authorized users or embedding origins | [Secure your Stream]([url-5]) |
| Broadcast live, replay recordings, or simulcast | [Live workflow routing](./api-live.md) |
| Check usage, costs, or upload constraints | [Analytics]([url-6]), [pricing]([url-7]), and [upload requirements]([url-2]) |

## In This Reference

- [configuration.md](./configuration.md): project setup and access decisions.
- [api.md](./api.md): upload, playback, editing, and library operations.
- [api-live.md](./api-live.md): live inputs, outputs, recording, and WebRTC.
- [patterns.md](./patterns.md): application workflow decisions.
- [gotchas.md](./gotchas.md): troubleshooting routes.
