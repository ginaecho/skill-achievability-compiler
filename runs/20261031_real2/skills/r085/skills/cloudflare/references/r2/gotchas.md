# R2 Gotchas & Troubleshooting

Use the current references to diagnose the actual response or error instead of copying a workaround.

| Symptom or decision | What to check |
|---------------------|---------------|
| Listing stops early or escapes the intended prefix | Follow `truncated` and the returned cursor, retaining the original prefix, delimiter, and metadata options on subsequent requests. See the listing section of the [Workers API reference]([url-1]). |
| Conditional read has no body, or conditional write returns null | Distinguish a missing object from a failed condition; choose the HTTP response for the actual request condition. See conditional operations in the [Workers API reference]([url-1]). |
| ETag, metadata, checksum, or stream upload behaves unexpectedly | Check supported values and return types in the [Workers API reference]([url-1]), the [Worker upload example]([url-2]), and [Workers streams]([url-3]). |
| Multipart upload fails or cannot be resumed | Check part constraints and handle an upload that has already completed or aborted: [multipart guide]([url-4]) and [API reference]([url-1]). |
| S3 authentication or signed URL fails | Verify credentials, endpoint, region, operation, signed headers, and expiry using [SDK setup]([url-5]), [authentication]([url-6]), and [presigned URLs]([url-7]). |
| Browser fails but an HTTP client succeeds | Check [CORS]([url-8]) and [troubleshooting]([url-9]). |
| Local and deployed data or behavior differ | Check [local development]([url-10]), [supported bindings]([url-11]), and the local persistence options in [Wrangler R2 commands]([url-12]). |
| Reads serve old or missing content after an update | Check the [consistency model and cache interactions]([url-13]). |
| Upload size, metadata size, storage cost, or lifecycle behavior is unexpected | Fetch [limits]([url-14]), [pricing]([url-15]), [storage classes]([url-16]), and [object lifecycles]([url-17]). |

For other failures, start with [R2 troubleshooting]([url-9]) and [error codes]([url-18]).
