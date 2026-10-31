# Static Assets Routing Patterns

Decide which requests need application logic before choosing configuration. Record expected behavior for public files, API paths, protected content, browser navigation, and missing URLs.

| Routing need | Documentation |
|--------------|---------------|
| Serve public assets with minimal Worker involvement | [Default Worker routing]([url-1]) |
| Combine a SPA with API routes | [Advanced SPA routing control]([url-2]) |
| Require authentication or transform assets before serving | [Run Worker before each request]([url-3]) |
| Route an OAuth callback or selected dynamic paths to the Worker | [Run Worker first for selective paths]([url-4]) |
| Select assets for locale or experiment variants | [Asset binding API]([url-5]) and [Worker-first routing]([url-6]) |
| Serve generated HTML with a custom 404 | [Custom 404 pages]([url-7]) |
| Apply static cache/security headers or redirects | [Custom headers]([url-8]) and [redirects]([url-9]) |

Keep public asset paths eligible for direct serving when they do not need application logic. Ensure protected paths cannot bypass the authorization handler through an asset match or navigation fallback. For locale or experiment routing, map accepted variants to known build outputs and define a fallback explicitly.

Use [configuration.md](configuration.md) for setup and [gotchas.md](gotchas.md) for representative request checks.
