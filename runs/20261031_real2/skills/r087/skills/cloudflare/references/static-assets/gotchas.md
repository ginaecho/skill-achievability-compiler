# Static Assets Gotchas

Compare the deployed build output and effective configuration with the exact request that failed. Test browser navigation separately from client-side fetches when investigating SPA routing.

| Symptom or decision | Documentation |
|---------------------|---------------|
| Asset missing or unexpected files uploaded | [Asset directory]([url-1]) and [ignore rules]([url-2]) |
| Worker is bypassed for an asset or protected path | [Worker-first routing]([url-3]) |
| Browser navigation returns HTML for an API path | [SPA navigation requests]([url-4]) and [advanced routing]([url-5]) |
| Unexpected redirects or trailing slashes | [HTML handling]([url-6]) |
| A missing route serves the wrong fallback | [SPA routing]([url-7]) or [SSG custom 404 pages]([url-8]) |
| Cache behavior or custom headers differ from expectations | [Default and custom headers]([url-9]) |
| Vite development and deployment behave differently | [Vite asset configuration and output]([url-10]) |
| Worker-first requests return 429 or affect cost | [Billing and limitations]([url-11]) |
| Asset count or file size exceeds deployment limits | [Static asset platform limits]([url-12]) |
| Placement adds latency to asset requests | [Worker routing and placement caveat]([url-3]) |

Verify a public asset, API endpoint, protected path, and missing URL against the routing intent. Inspect response status, redirect location, and cache headers before changing fallback or cache configuration. Return to [configuration.md](configuration.md) and [api.md](api.md) for the relevant settings and binding behavior.
