# R2 Patterns & Best Practices

Choose the access and delivery model, then fetch the implementation guide.

| Task | Current documentation |
|------|-----------------------|
| Stream object downloads or accept uploads through a Worker | [Use R2 from Workers]([url-1]) |
| Add conditional reads/writes, range handling, checksums, or batch deletion | [Workers API reference]([url-2]) |
| Upload large files with multipart state tracked by the client | [Multipart Worker and client example]([url-3]) |
| Upload directly from a browser or share a temporary download | [Presigned URLs]([url-4]) and [CORS]([url-5]) |
| Cache responses served by a Worker | [Cache API example]([url-6]) |
| Deliver public objects through a custom domain or evaluate [host-1] | [Public buckets]([url-7]) |
| Process object changes asynchronously | [Event notifications]([url-8]) and [Queues](../queues/) |
| Expire objects or transition storage classes | [Object lifecycles]([url-9]) and [storage classes]([url-10]) |

Authorize the caller for the selected object key and operation before exposing a Worker endpoint or issuing a presigned URL. A key-format check alone does not establish access rights. Set the intended expiry and signed request constraints for temporary access; configure browser CORS separately.

Keep private responses out of shared public caches. Choose cache keys and invalidation around the application's access model, and check [R2 consistency and caching behavior]([url-11]) when objects can change. For multipart uploads, plan for failed parts, completion, and cleanup using the linked guide.
