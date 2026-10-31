# DataForSEO

Comprehensive SEO data API for SERP results, keyword research, backlinks, and on-page analysis.

## Capabilities

| Integration | Available | Notes |
|-------------|-----------|-------|
| API | ✓ | SERP, Keywords Data, Backlinks, On-Page, Labs |
| MCP | - | Not available |
| CLI | ✓ | [dataforseo.js](../clis/dataforseo.js) |
| SDK | ✓ | Python, TypeScript, PHP, Java, C# |

## Authentication

- **Type**: Basic Auth
- **Header**: `Authorization: Basic {base64(login:password)}`
- **Get credentials**: API Access tab at [url-1]
- **Note**: API password is auto-generated, different from account password

## Common Agent Operations

### SERP - Google organic (live)

```bash
POST [url-2]

[{
  "keyword": "marketing automation",
  "location_name": "United States",
  "language_name": "English"
}]
```

### Keywords - Search volume (live)

```bash
POST [url-3]

[{
  "keywords": ["email marketing", "marketing automation", "crm software"],
  "location_code": 2840,
  "language_code": "en"
}]
```

### Keywords - Keywords for site (live)

```bash
POST [url-4]

[{
  "target": "[host-1]",
  "location_code": 2840,
  "language_code": "en"
}]
```

### Backlinks - Summary

```bash
POST [url-5]

[{
  "target": "[host-1]",
  "internal_list_limit": 10,
  "backlinks_status_type": "live"
}]
```

### Backlinks - List

```bash
POST [url-6]

[{
  "target": "[host-1]",
  "mode": "as_is",
  "limit": 100,
  "backlinks_status_type": "live"
}]
```

### Backlinks - Referring domains

```bash
POST [url-7]

[{
  "target": "[host-1]",
  "limit": 100
}]
```

### Backlinks - Index (database stats)

```bash
GET [url-8]
```

### On-Page - Instant pages audit

```bash
POST [url-9]

[{
  "url": "[url-10]",
  "enable_javascript": true
}]
```

### SERP - Locations list

```bash
GET [url-11]
```

### SERP - Languages list

```bash
GET [url-12]
```

## API Pattern

DataForSEO uses two methods for most endpoints:
- **Live** (`/live`) - Synchronous, results in same response
- **Task-based** (`/task_post` + `/task_get/$id`) - Async for large requests

Request bodies are always JSON arrays (even for single requests).

## Key Metrics

### Keyword Metrics
- `search_volume` - Monthly search volume
- `competition` - Competition level (0-1)
- `cpc` - Cost per click
- `monthly_searches` - Monthly breakdown array

### Backlink Metrics
- `total_backlinks` - Total backlink count
- `referring_domains` - Unique referring domains
- `domain_rank` - Domain authority score
- `backlinks_spam_score` - Spam score

## When to Use

- Programmatic SERP tracking at scale
- Keyword research with search volume data
- Backlink analysis and monitoring
- On-page SEO audits
- Competitor analysis

## Rate Limits

- Rate limit headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`
- Backlinks API: 2000 requests/minute, 30 simultaneous
- Varies by endpoint and plan

## Relevant Skills

- seo-audit
- programmatic-seo
- content-strategy
- competitors

### CLI market selection

For `serp google`, `--location-code` and `--language-code` select API codes
instead of location/language names. Explicit codes take precedence over name
flags; omitted flags retain United States and English. Preview the paid request
with `--dry-run`:

```bash
node tools/clis/dataforseo.js serp google --keyword chaussures \
  --location-code 2250 --language-code fr --dry-run
```
