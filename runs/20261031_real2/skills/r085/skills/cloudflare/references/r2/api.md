# R2 API Reference

Fetch the relevant page before writing code. Use the Workers API for bucket bindings and the S3 API for S3 clients; their types and semantics differ.

| Task | Current documentation |
|------|-----------------------|
| Read, write, inspect, delete, or list objects; metadata, checksums, ranges, and return types | [Workers API reference]([url-1]) |
| Implement a Worker that serves or writes objects | [Use R2 from Workers]([url-2]) |
| Create, resume, complete, or abort multipart uploads | [Multipart Worker and client example]([url-3]) |
| Check supported S3 operations and headers | [S3 compatibility]([url-4]) |
| Configure an S3 JavaScript client | [AWS SDK for JavaScript v3]([url-5]) |
| Sign temporary upload or download access | [Presigned URLs]([url-6]) |
| Encrypt with customer-provided keys | [SSE-C usage]([url-7]) |
| Manage buckets and objects from the command line | [Wrangler R2 commands]([url-8]) |

Use generated project types rather than maintaining local copies of R2 interfaces; see [Workers TypeScript guidance]([url-9]). For pagination and conditional response handling, read [gotchas.md](./gotchas.md) alongside the API reference.
