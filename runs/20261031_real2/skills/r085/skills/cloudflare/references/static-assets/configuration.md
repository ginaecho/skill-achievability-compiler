# Static Assets Configuration

Inspect the build script, output directory, Wrangler configuration, and any framework-generated deployment configuration first. Configure the files actually produced by the build, and identify which paths need Worker logic.

| Task | Documentation |
|------|---------------|
| Set the asset directory and exclude non-public files | [Directory]([url-1]) and [ignoring assets]([url-2]) |
| Make assets available to Worker code | [Asset binding configuration]([url-3]) |
| Select paths that must run Worker logic before asset serving | [Worker-first configuration]([url-4]) |
| Configure SPA fallback and navigation behavior | [SPA configuration]([url-5]) |
| Configure generated HTML and missing-page responses | [SSG configuration]([url-6]) |
| Choose canonical HTML URLs and trailing slash handling | [HTML handling modes]([url-7]) |
| Configure assets produced by the Cloudflare Vite plugin | [Vite asset configuration]([url-8]) |
| Configure static response headers or redirects | [Headers]([url-9]) and [redirects]([url-10]) |

For Vite projects, inspect generated output before overriding asset paths. For protected routes, ensure that the selected routing configuration reaches the authorization logic before returning an asset. Use [patterns.md](patterns.md) to decide routing intent and [gotchas.md](gotchas.md) to verify it.
