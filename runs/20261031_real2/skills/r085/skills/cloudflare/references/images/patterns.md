# Images Patterns

Choose the workflow that matches the existing storage and delivery architecture, then read its implementation guide.

| Workflow | Documentation |
|----------|---------------|
| Let users upload without exposing account credentials | [Direct Creator Upload]([url-1]) |
| Serve images for different layouts and display densities | [Make responsive images]([url-2]) |
| Select output format for hosted images | [Hosted-image format optimization]([url-3]) |
| Select output format for a Worker pipeline | [Workers optimization binding]([url-4]) |
| Optimize user uploads, add a watermark, and store the result in R2 | [Transform user-uploaded images before uploading to R2]([url-5]) |
| Compose overlays and watermarks | [Draw overlays]([url-6]) |
| Cache a Worker transformation response | [Binding methods and caching guidance]([url-7]) |
| Configure hosted-image browser caching | [Browser TTL]([url-8]) |

Adapt dimensions and quality to the actual layout and representative source images. Keep upload credentials server-side, preserve the application's access checks, and validate both the resulting image and its response headers. Consult [limits and troubleshooting](gotchas.md) before choosing batch sizes or retry behavior.
