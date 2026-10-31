# Images API Selection

| Operation | Documentation |
|-----------|---------------|
| Optimize image bytes in a Worker; select input, transform, output, and response methods | [Optimize with Workers]([url-1]) |
| Upload, list, retrieve, update, or delete hosted images from a Worker | [Manage hosted images with Workers]([url-2]) |
| Upload or manage images through HTTP | [Upload methods]([url-3]) and its linked Images API reference |
| Accept uploads directly from a client | [Direct Creator Upload]([url-4]) |
| Construct hosted-image delivery URLs | [Serve uploaded images]([url-5]) |
| Apply URL optimization parameters or select fit, quality, and format | [Optimization features]([url-6]) |
| Draw overlays or watermarks | [Draw overlays]([url-7]) |

Do not transfer URL parameters or HTTP request shapes directly into binding calls. Read the contract for the selected interface, including output format handling. Use the project's generated binding types and existing error handling. See [configuration](configuration.md) for setup and [troubleshooting](gotchas.md) for failures and limits.
