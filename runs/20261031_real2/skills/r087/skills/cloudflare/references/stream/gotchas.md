# Stream Gotchas

Identify whether the failure occurs during upload, encoding, authorization, playback, or live ingestion before changing configuration. Read the linked requirements and error guidance for that stage.

| Symptom or check | Read |
|---|---|
| Unsupported file or upload constraint failure | [Supported formats and upload requirements]([url-1]) |
| Large upload fails or restarts after interruption | [Resumable upload requirements]([url-2]) |
| Stream cannot fetch an imported video | [Upload via link requirements]([url-3]) |
| Upload finished but video is not playable | [Upload progress tracking]([url-4]) and [processing error codes]([url-5]) |
| Private playback or embedding fails | [Signed tokens, restrictions, and allowed origins]([url-6]) |
| Webhook signature verification fails | [Verify the raw body and signature]([url-7]) |
| A custom HLS/DASH player behaves incorrectly | [Own-player integration and manifest handling]([url-8]) |
| Live stream will not connect or playback buffers | [Live troubleshooting]([url-9]) |
| Simulcast output does not behave as expected | [Output configuration and limits]([url-10]) |
| Estimate storage or delivery costs | [Stream pricing]([url-11]) |

Check the actual response and current docs before adopting a retry policy or treating a video as ready. Keep credentials out of browser code and logs; use [configuration.md](./configuration.md) for access setup and [patterns.md](./patterns.md) for state decisions.
