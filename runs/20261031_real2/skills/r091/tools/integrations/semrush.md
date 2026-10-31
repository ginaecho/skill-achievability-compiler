# SEMrush

SEO and competitive analysis platform for keyword research and site audits.

## Capabilities

| Integration | Available | Notes |
|-------------|-----------|-------|
| API | ✓ | Analytics API, Projects API |
| MCP | ✓ | Official remote server at `[url-1]`: OAuth 2.1, or an API key in the Authorization header ([docs]([url-2])), checked 2026-10-27 |
| CLI | - | Not available |
| SDK | - | API-only |

## Authentication

- **Type**: API Key
- **Parameter**: `key={api_key}` in query string
- **Get key**: My Profile > API in SEMrush dashboard

## Common Agent Operations

### Domain overview

```bash
GET [url-3]}&export_columns=Db,Dn,Rk,Or,Ot,Oc,Ad,At,Ac&domain=[host-1]
```

### Organic keywords

```bash
GET [url-4]}&export_columns=Ph,Po,Pp,Pd,Nq,Cp,Ur,Tr,Tc,Co,Nr&domain=[host-1]&database=us&display_limit=100
```

### Keyword overview

```bash
GET [url-5]}&export_columns=Ph,Nq,Cp,Co,Nr&phrase=keyword&database=us
```

### Related keywords

```bash
GET [url-6]}&export_columns=Ph,Nq,Cp,Co,Nr,Td&phrase=keyword&database=us&display_limit=50
```

### Keyword difficulty

```bash
GET [url-7]}&export_columns=Ph,Kd&phrase=keyword&database=us
```

### Backlinks overview

```bash
GET [url-8]}&target=[host-1]&target_type=root_domain
```

### Backlinks list

```bash
GET [url-9]}&target=[host-1]&target_type=root_domain&export_columns=source_url,source_title,target_url,anchor&display_limit=100
```

### Competitors

```bash
GET [url-10]}&export_columns=Dn,Cr,Np,Or,Ot,Oc,Ad&domain=[host-1]&database=us&display_limit=20
```

## Response Format

Responses are CSV by default. Add `&export_escape=1` for proper escaping.

## Export Columns

### Domain Report
- `Db` - Database
- `Dn` - Domain
- `Rk` - Rank
- `Or` - Organic keywords
- `Ot` - Organic traffic
- `Oc` - Organic cost

### Keyword Report
- `Ph` - Phrase/keyword
- `Nq` - Search volume
- `Cp` - CPC
- `Co` - Competition
- `Kd` - Keyword difficulty
- `Nr` - Number of results

### Backlinks
- `source_url` - Linking page
- `target_url` - Target page
- `anchor` - Anchor text
- `source_title` - Page title

## Databases

Use country code: `us`, `uk`, `de`, `fr`, `ca`, `au`, etc.

## When to Use

- Keyword research
- Competitive analysis
- Backlink analysis
- Site audits
- Rank tracking
- Content gap analysis

## Rate Limits

- Varies by plan (10-30K units/day)
- Each API call costs units

## Relevant Skills

- seo-audit
- programmatic-seo
- content-strategy
- competitors

### CLI CSV decoding

The [Semrush CLI](../clis/semrush.js) requests `export_escape=1` and decodes the
semicolon-separated report into JSON objects. Quoted headers/cells, escaped
quotes, and line breaks inside cells are preserved as field values.
