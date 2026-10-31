# Pages Troubleshooting

Identify whether the failure occurs during the build, asset serving, or Function execution before changing configuration.

| Task | Documentation |
| --- | --- |
| Build output is missing or incorrect | [Build configuration]([url-1]) |
| A static URL redirects or returns an unexpected 404 | [Serving Pages]([url-2]) |
| Static response headers are not applied | [Headers]([url-3]) |
| A redirect rule does not match | [Redirects]([url-4]) |
| Investigate a failed Function request | [Debugging and logging]([url-5]) |
| Check deployment and file capacity | [Pages limits]([url-6]) |
| Understand Function versus static request billing | [Functions pricing]([url-7]) |

Compare the same route in local, preview, and production environments; record the build output and configuration used by each. See [Pages Functions troubleshooting](../pages-functions/gotchas.md) for handler and binding issues.

## Framework-Specific

Fetch the relevant [framework guide]([url-8]) before changing adapters or recommending another host. For a move to Workers, follow the [migration guide]([url-9]).
