# Stream API Reference

Read the task-specific documentation for request schemas, SDK examples, and response fields. For live inputs and outputs, use [api-live.md](./api-live.md).

| Task | Read |
|---|---|
| Issue a one-time upload URL to an end user | [Direct creator uploads]([url-1]) |
| Resume uploads or handle unreliable connections | [Resumable uploads and requirements]([url-2]) |
| Import a video already hosted elsewhere | [Upload via link]([url-3]) |
| Embed an iframe or React player | [Use the Stream Player]([url-4]) |
| Use HLS/DASH with an existing player | [Use your own player]([url-5]) |
| Issue playback tokens | [Signed URLs and token-generation choices]([url-6]) |
| Generate previews or downloadable files | [Thumbnails]([url-7]) and [downloads]([url-8]) |
| Upload captions or generate them with Stream | [Add captions]([url-9]) |
| Apply branding during upload | [Watermarks]([url-10]) |
| Trim an on-demand video | [Video clipping]([url-11]) |
| List and filter videos through the REST API | [List videos]([url-12]) |
| Manage videos from a Worker | [Stream binding methods]([url-13]) |
| React to encoding success or failure | [Video webhooks]([url-14]) |

Keep the returned video UID associated with the application's owning user or record. Treat upload completion and playback readiness as separate application states; see [workflow decisions](./patterns.md).
