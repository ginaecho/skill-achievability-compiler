# Images Troubleshooting

First identify whether the failure involves hosted-image storage, remote URL transformations, or a Worker binding. Capture the failing operation, response status, relevant headers, and error message before changing options.

| Symptom or question | Documentation |
|---------------------|---------------|
| Resizing is absent, an origin request fails, or a transformation returns an error code | [Troubleshooting]([url-1]) |
| Input size, dimensions, animation, or format compatibility | [Limits and formats]([url-2]) — choose the section for the affected interface |
| Unexpected fit, quality, format, or crop behavior | [Optimization features]([url-3]) |
| Binding input, output, or response handling fails | [Binding methods]([url-4]) |
| Local behavior differs from production | [Local binding development]([url-5]) |
| Private delivery fails or an image is unexpectedly public | [Serve private images]([url-6]) and [variant public access]([url-7]) |
| Remote transformations appear stale | [Caching and purging]([url-8]) |
| Worker transformations repeat unnecessarily | [Binding caching guidance]([url-4]) |

Do not apply one interface's limits, error codes, or caching rules to another. Reproduce with a representative image and verify the chosen fix using the project's existing checks. Retry only after identifying a transient failure; changing invalid inputs or access configuration requires a different fix. See [API selection](api.md) and [configuration](configuration.md) when the wrong interface or setup is responsible.
