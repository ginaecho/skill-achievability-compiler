# AI Search Troubleshooting Routes

| Symptom or question | Documentation |
|---------------------|---------------|
| API request fails, including authentication or missing instances | [API error codes]([url-1]) |
| Upload or sync succeeds but content fails during processing | [Indexing error codes]([url-2]) |
| Content is missing or stale | [Syncing]([url-3]) and [supported data sources and formats]([url-4]) |
| Filters return unexpected documents or no matches | [Filtering]([url-5]) and [metadata attributes]([url-6]) |
| Thresholds exclude results or responses need tuning | [Result controls]([url-7]) |
| Binding types, response parsing, or streaming fail after an upgrade | [Workers binding migration]([url-8]) |
| Capacity, file-size, or billing questions | [Limits and pricing]([url-9]) |

For legacy binding behavior, start with [API routes](api.md). Do not apply current filter syntax or response shapes to legacy calls without following the migration guide.
