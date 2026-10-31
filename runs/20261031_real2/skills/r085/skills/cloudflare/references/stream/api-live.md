# Stream Live Streaming API

Choose the ingest protocol and viewer experience before creating live inputs. Read the current examples for returned endpoints and credentials instead of constructing publish URLs from an input ID.

| Task | Read |
|---|---|
| Create an RTMPS/SRT input and connect an encoder | [Start a live stream]([url-1]) |
| Update inputs, recording, retention, or stream keys | [Manage live inputs]([url-2]) |
| Choose persistent-channel playback versus a particular video | [View by live input ID or video ID]([url-3]) |
| Find and replay recorded broadcasts | [Replay recordings]([url-4]) |
| Forward broadcasts to external platforms | [Simulcasting configuration and limits]([url-5]) |
| Receive connection and disconnection notifications | [Live webhooks]([url-6]) |
| Publish and play using WHIP/WHEP | [WebRTC requirements and endpoints]([url-7]) and [browser integration]([url-8]) |
| Diagnose encoder, buffering, or latency problems | [Live troubleshooting]([url-9]) |

Keep publishing credentials separate from viewer playback data. Decide whether the application stores a reusable live input, individual recording IDs, or both. Route recording processing events through [video webhooks]([url-10]); live connection events have their own notification setup.

See [configuration.md](./configuration.md) for access decisions and [patterns.md](./patterns.md) for application state handling.
