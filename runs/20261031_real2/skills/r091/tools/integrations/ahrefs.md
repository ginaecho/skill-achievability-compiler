# Ahrefs

SEO toolset for backlink analysis, keyword research, and competitive research.

## Capabilities

| Integration | Available | Notes |
|-------------|-----------|-------|
| API | ✓ | REST API for Site Explorer, Keywords Explorer |
| MCP | ✓ | Official remote server at `[url-1]` ([docs]([url-2])); the older local npm server is archived, checked 2026-10-27 |
| CLI | - | Not available |
| SDK | - | API-only |

## Authentication

- **Type**: API Token
- **Header**: `Authorization: Bearer {api_token}`
- **Get token**: Account Settings > API in Ahrefs dashboard

## Common Agent Operations

### Domain rating

```bash
GET [url-3]

Authorization: Bearer {api_token}
```

### Backlinks overview

```bash
GET [url-4]

Authorization: Bearer {api_token}
```

### Referring domains

```bash
GET [url-5]

Authorization: Bearer {api_token}
```

### Backlinks list

```bash
GET [url-6]

Authorization: Bearer {api_token}
```

### Organic keywords

```bash
GET [url-7]

Authorization: Bearer {api_token}
```

### Top pages

```bash
GET [url-8]

Authorization: Bearer {api_token}
```

### Keyword overview

```bash
GET [url-9]

Authorization: Bearer {api_token}
```

### Keyword suggestions

```bash
GET [url-10]

Authorization: Bearer {api_token}
```

### SERP overview

```bash
GET [url-11]

Authorization: Bearer {api_token}
```

## Key Metrics

### Domain Metrics
- `domain_rating` - Domain Rating (DR)
- `ahrefs_rank` - Ahrefs Rank
- `referring_domains` - Referring domains count
- `backlinks` - Total backlinks
- `organic_traffic` - Estimated organic traffic

### Keyword Metrics
- `volume` - Monthly search volume
- `keyword_difficulty` - KD score (0-100)
- `cpc` - Cost per click
- `clicks` - Estimated monthly clicks
- `global_volume` - Global search volume

### Backlink Fields
- `url_from` - Source URL
- `url_to` - Target URL
- `anchor` - Anchor text
- `domain_rating_source` - Source DR
- `first_seen` - First discovery date

## Modes

- `domain` - Entire domain
- `subdomains` - Domain + subdomains
- `prefix` - URL prefix
- `exact` - Exact URL

## When to Use

- Backlink analysis
- Link building research
- Keyword research
- Competitive analysis
- Content gap analysis
- Site audits

## Rate Limits

- Varies by plan
- 500-5000 rows per request

## Relevant Skills

- seo-audit
- content-strategy
- competitors

## Dated reports in the CLI

`domain-rating get`, `keywords organic`, and `top-pages list` accept an explicit
`--date YYYY-MM-DD`, defaulting to today's UTC date when omitted. Organic
keywords and top pages supply default columns; `--select` overrides them.
The CLI validates calendar dates and rejects empty column lists before a request.
Choose fields from the provider response schema:

- [Domain rating]([url-12])
- [Organic keywords]([url-13])
- [Top pages]([url-14])

## Backlink report columns

`backlinks list` calls `all-backlinks` and defaults to
`url_from,url_to,anchor,is_dofollow`. `refdomains list` defaults to
`domain,domain_rating,links_to_target`. Both APIs require `select`; use
`--select` to choose other columns. These defaults omit columns marked with
additional unit costs in the schemas. Requests still consume API units.

- [Backlinks]([url-15])
- [Refdomains]([url-16])
