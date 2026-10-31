# Stream Patterns

Use the official workflow examples after identifying where the existing application handles authorization, video ownership, and processing state.

| Workflow | Read |
|---|---|
| Browser uploads through a server-issued URL | [Direct creator uploads]([url-1]) |
| Large or interruption-prone uploads | [Resumable uploads]([url-2]) |
| Update application state when processing completes | [Video webhooks]([url-3]) and [upload progress tracking]([url-4]) |
| Verify an incoming processing notification | [Webhook authenticity]([url-5]) |
| Embed playback in a React application | [Stream Player and framework integrations]([url-6]) |
| Serve private videos | [Signed playback and signing examples]([url-7]) |
| Broadcast from a browser | [Browser-based WebRTC]([url-8]) |

## Application Decisions

- Check the user's permission before issuing upload URLs or playback tokens. Decide how uploaded video IDs map to application records and who may later view or delete them.
- Model uploading, processing, ready, and failed states in the UI. Use documented status and notification data; select retry and timeout policies to suit the application instead of assuming a fixed encoding deadline.
- Preserve the raw webhook request body for verification before applying state changes. Decide how the application's existing event handling reconciles notifications with stored video records.
- For live playback, decide whether viewers follow a channel across broadcasts or open a specific recording; see [live workflows](./api-live.md).

See [configuration.md](./configuration.md) for setup and [gotchas.md](./gotchas.md) for diagnosis.
