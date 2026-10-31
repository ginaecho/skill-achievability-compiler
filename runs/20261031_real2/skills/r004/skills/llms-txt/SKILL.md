---
name: llms-txt
description: >
  Generate, validate, and optimize llms.txt files that make websites and
  documentation LLM-friendly. Handles full-suite creation including companion
  files (llms-full.txt, llms-small.txt) and strategic advice on implementation
  patterns. Use when user says "create an llms.txt", "generate llms.txt for my
  site", "audit my llms.txt", "make my docs LLM-friendly", "llms-full.txt",
  or any llms.txt-related task.
license: MIT
---

# llms.txt Generator

Generate, validate, and optimize llms.txt files -- the Markdown-formatted standard that gives LLMs a curated, context-window-friendly overview of a website's most important content.

Before starting, consult [references/llmstxt-guide.xml](references/llmstxt-guide.xml) -- a comprehensive playbook covering the official specification, five implementation patterns, companion file conventions, best practices, a validation checklist, and the full tooling ecosystem. Reference it throughout the workflow.

## Workflow Overview

```
Discovery --> Strategy --> Generate llms.txt --> Companion Files --> Validate --> Deliver
    ^                           |                                       |
    +--------- Refine ---------+                                       |
                                +-------------- Fix issues ------------+
```

Follow steps 1-6 in order. Steps may loop if the user wants revisions or validation surfaces issues.

## Step 1: Discovery

Gather context about the user's site or project. Ask about:

- **Site type** -- Documentation site, SaaS product, e-commerce, open-source library, personal site, or multi-product organization?
- **Content structure** -- What are the key pages and content areas? (docs, API references, tutorials, guides, blog, pricing)
- **Audience** -- Developers, end-users, or mixed? Who will be feeding this to an LLM?
- **Technical stack** -- What framework or CMS? Do pages have `.md` versions available?
- **Goal** -- AI coding assistant context (Cursor, Windsurf), generative engine presence, future-proofing, or all of the above?
- **Existing file** -- Do they already have an llms.txt they want audited or improved?

Keep discovery concise: 3-5 questions max in one message. If the user provides a URL, explore the site structure to identify key content areas.

If the user already has an llms.txt file and wants an audit, skip to Step 5 (Validate).

## Step 2: Strategy

Based on discovery, recommend an implementation pattern. See `<implementation_patterns>` in llmstxt-guide.xml for full details and a decision tree:

| Pattern | Best for | Example |
|---------|----------|---------|
| Minimal index | Small sites, modular docs | Supabase (~100 tokens, links to per-topic files) |
| Comprehensive directory | Large multi-product sites | Vercel, Cloudflare (deep nesting, extensive links) |
| Dual-file | Medium-to-large docs sites | Anthropic, Stripe (llms.txt index + llms-full.txt) |
| Product-segmented | Multi-product orgs | Cloudflare (per-product llms-full.txt files) |
| Multi-site | Orgs with distinct web properties | Stripe (separate files for marketing vs docs) |

**Recommend companion files based on context** (see `<companion_files>` in llmstxt-guide.xml):

- **llms-full.txt** -- Recommended for most sites. Contains all documentation content in a single Markdown file. AI agents visit llms-full.txt over 2x more frequently than llms.txt.
- **llms-small.txt** -- Useful when targeting constrained context windows. Contains only page structure and titles.
- **Per-topic files** -- Useful for modular documentation (e.g., `/llms/guides.txt`, `/llms/api.txt`).

Present the recommendation with rationale. Confirm with the user before proceeding.

## Step 3: Generate llms.txt

Build the llms.txt file following the specification strictly (see `<specification>` in llmstxt-guide.xml for the authoritative rules and canonical example). The file has four sections in this exact order:

### Section 1: H1 Header (required)

```markdown
# Project Name
```

The only required element. Use the project or site name.

### Section 2: Blockquote Summary

```markdown
> A concise summary that gives an LLM immediate context about what this
> project or site is, what it does, and why someone would use it.
```

Include key information needed to understand the rest of the file. This is the single most important piece of context for an LLM.

### Section 3: Freeform Context (optional)

Plain Markdown paragraphs or lists (no headings) providing additional project context -- important caveats, compatibility notes, or constraints.

### Section 4: H2 Sections with Link Lists

Organize curated links under H2 headings. Each list item must have a hyperlink, optionally followed by a colon and descriptive notes:

```markdown
## Docs

- [Quickstart Guide]([url-1]): A 5-minute tutorial for getting your first project running with authentication and basic CRUD
- [API Reference]([url-2]): Complete REST API documentation covering all endpoints, request formats, and error codes
```

**Apply these best practices when generating** (see `<best_practices>` in llmstxt-guide.xml for the full rules):

- **Be a curator, not a collector** -- List the "greatest hits," not every page. This is not a sitemap.
- **Write descriptive link text** -- `[Quickstart Guide](url): A 5-minute tutorial...` not `[Docs](url)`.
- **Keep descriptions to 10-20 words** -- Factual and value-oriented.
- **Link to .md versions** where possible -- Markdown is up to 10x more token-efficient than HTML.
- **Most important sections first** -- Core docs, API reference, getting started before blog posts.
- **Use the Optional section strategically** -- Place secondary content that can be dropped when context is tight.

```markdown
## Optional

- [Changelog]([url-3]): Release history with breaking changes and migration notes
- [Advanced Configuration]([url-4]): Deep-dive into environment variables and custom plugins
```

**Content to include:** Core documentation, API references, getting-started guides, FAQs, key tutorials, pricing pages, key blog posts.

**Content to exclude:** Login pages, admin panels, user-generated content, gated/premium content, duplicate pages.

## Step 4: Companion Files

Based on the strategy from Step 2, generate companion files as needed.

### llms-full.txt

Compile referenced documentation content into a single Markdown file. Structure it with clear H1/H2 headers mirroring the llms.txt sections. Each section contains the full rendered content of the linked pages.

If the user cannot provide full page content, generate a structured skeleton with clear placeholders:

```markdown
# Project Name -- Full Documentation

## Quickstart Guide

[Paste or generate full quickstart content here]

## API Reference

[Paste or generate full API reference content here]
```

Advise the user on token budget -- note that Anthropic's llms-full.txt is ~481K tokens and Cloudflare's is ~3.7M tokens. Most sites should aim for the range their target LLM context window can handle.

### llms-small.txt

Generate an ultra-compact version with only the structural outline and page titles:

```markdown
# Project Name

> One-sentence summary.

## Docs
- Quickstart Guide
- API Reference
- Authentication

## Examples
- Todo App Tutorial
- E-commerce Integration
```

### Per-topic files

If the segmented pattern was chosen, generate separate files for each product or topic area (e.g., `/llms/guides.txt`, `/llms/js-sdk.txt`, `/llms/python-sdk.txt`).

## Step 5: Validate

Audit the generated file (or an existing user-provided file) against the specification and best practices. See `<validation_checklist>` in llmstxt-guide.xml for the complete checklist. Check each item and report findings.

### Specification compliance

- [ ] H1 header with project/site name is present (only required element)
- [ ] Blockquote summary follows the H1
- [ ] Freeform context (if any) uses paragraphs/lists only, no headings
- [ ] H2 sections contain properly formatted link lists
- [ ] Links use the format `[name](url)` with optional `: description`
- [ ] Section order follows the specification (H1, blockquote, freeform, H2 sections)
- [ ] `## Optional` section used correctly (only for skippable content)
- [ ] Valid Markdown syntax throughout

### Content quality

- [ ] Summary blockquote provides enough context for an LLM to understand the project
- [ ] Curated selection, not an exhaustive sitemap dump
- [ ] Link descriptions are 10-20 words, factual, and value-oriented
- [ ] Links point to .md versions where available
- [ ] Most important content appears in the first sections
- [ ] No login pages, admin panels, or gated content
- [ ] Reasonable total size (estimate token count; flag if unusually large or small)

### The paste test

Recommend the user validate by pasting the file contents into ChatGPT or Claude (with web search disabled) and asking questions about their product. If the model gives poor answers, the file needs revision.

Present validation results as a checklist with pass/fail status and specific recommendations for any issues found.

## Step 6: Deliver

Present the final file(s) and provide implementation guidance.

### Implementation instructions

- Host at domain root: `[host-1]`
- Serve with MIME type `text/plain`
- Place companion files alongside: `[host-2]`, `[host-3]`
- For subpath documentation: `[host-4]` is also valid

### Framework-specific guidance

Recommend relevant tooling based on the user's stack (see `<tooling_ecosystem>` in llmstxt-guide.xml for the full catalog):

| Stack | Tooling |
|-------|---------|
| Mintlify | Auto-generated, zero config needed |
| GitBook | Auto-generated for all published docs |
| VitePress | `vitepress-plugin-llms` |
| Docusaurus | `docusaurus-plugin-llms` |
| Astro | `@4hse/astro-llms-txt` |
| Next.js | `next-llms-txt` or manual placement in `public/` |
| Hugo | Place in `/static/llms.txt` |
| Jekyll | Place in root directory |
| WordPress | Yoast SEO (built-in), AIOSEO, or "Website LLMs.txt" plugin |
| Manual | Place file at web server root or configure routing |

### Maintenance checklist

Advise the user to update their llms.txt when they:

- Add, remove, or significantly restructure documentation pages
- Launch new product areas or features with documentation
- Change URLs or site architecture
- Add new SDK/language support

### Next steps summary

Present a numbered list of concrete actions:

1. Deploy the generated file(s) to the site root
2. Verify the file is accessible at `[host-1]`
3. Run the paste test (Step 5) to validate quality
4. Set up `.md` page versions if not already available
5. Add to the llms-txt-hub directory on GitHub for discoverability
6. Schedule periodic reviews (quarterly or on major doc changes)

## Examples

### Example 1: Open-source library

User says: "Create an llms.txt for my Python image processing library called PixelForge"

Actions:
1. Ask about documentation structure, key pages, and whether docs have .md versions
2. Recommend the dual-file pattern (llms.txt index + llms-full.txt)
3. Generate llms.txt with sections for Docs, API Reference, Examples, and Optional
4. Generate llms-full.txt skeleton with content placeholders
5. Validate both files against the specification
6. Deliver with instructions for placing in the docs site root

Result:

```markdown
# PixelForge

> PixelForge is a Python library for high-performance image processing, offering
> GPU-accelerated filters, batch transformations, and a composable pipeline API.

- PixelForge requires Python 3.10+ and supports CUDA 12.x for GPU acceleration
- The pipeline API is inspired by scikit-image but is not API-compatible

## Docs

- [Quickstart]([url-5]): Install PixelForge and run your first image pipeline in under 5 minutes
- [Pipeline API Guide]([url-6]): Composable transformation chains with lazy evaluation and automatic GPU offloading
- [API Reference]([url-7]): Complete reference for all modules, classes, and functions

## Examples

- [Batch Processing]([url-8]): Process 10,000 images with parallel pipelines and progress tracking
- [Custom Filters]([url-9]): Build reusable filter functions with the kernel API

## Optional

- [Changelog]([url-10]): Release history with migration guides for breaking changes
- [Benchmark Suite]([url-11]): Performance comparisons against Pillow, OpenCV, and scikit-image
```

### Example 2: Auditing an existing llms.txt

User says: "Can you audit my llms.txt file? Here it is: [pastes file]"

Actions:
1. Skip discovery and strategy (Steps 1-2)
2. Skip generation (Steps 3-4)
3. Run full validation (Step 5) against specification and best practices
4. Present checklist with pass/fail for each item
5. Provide specific rewrite suggestions for any issues

Result: A validation report with findings like:
- PASS: H1 header present
- PASS: Blockquote summary present
- FAIL: Link descriptions are too generic ("API docs" -- add 10-20 word descriptions)
- FAIL: Links point to HTML pages, not .md versions
- WARN: No `## Optional` section -- consider moving secondary content there
- RECOMMENDATION: Add llms-full.txt companion file for complete content delivery

### Example 3: Multi-product organization

User says: "I need llms.txt for my company -- we have 4 products: an API gateway, a CDN, a database, and a serverless platform"

Actions:
1. Discovery: understand each product's documentation structure and target audience
2. Recommend the product-segmented pattern with a root llms.txt index
3. Generate root llms.txt linking to per-product documentation
4. Generate per-product llms-full.txt files (e.g., `/api-gateway/llms-full.txt`)
5. Generate llms-small.txt for the constrained context window use case
6. Validate all files and deliver with deployment instructions

Result: A root llms.txt organized by product with H2 sections for each, plus four per-product llms-full.txt companion files and one llms-small.txt for the top-level overview.

## Troubleshooting

### Issue: File is too large for useful context

Cause: Including too many links turns llms.txt into a sitemap rather than a curated index.
Solution: Ruthlessly curate. Move secondary content to `## Optional`. Consider the minimal index pattern with per-topic companion files. The llms.txt file itself should be a "greatest hits" -- aim for tens of links, not hundreds.

### Issue: Links point to HTML instead of Markdown

Cause: The site does not serve `.md` versions of pages.
Solution: Check if the framework supports `.md` URL variants (many documentation platforms do). If not, advise the user to set up Markdown page versions -- the specification recommends appending `.md` to existing URLs (e.g., `[host-5]`). As a fallback, HTML links still work but are less token-efficient.

### Issue: Missing or weak blockquote summary

Cause: The summary is omitted or too brief to give an LLM useful context.
Solution: Write a 2-4 sentence blockquote that answers: What is this project? What does it do? Who is it for? What key constraints should an LLM know? This is the single most impactful element for LLM comprehension.

### Issue: Generic link descriptions

Cause: Descriptions like "API docs" or "Guide" do not help an LLM decide which link to follow.
Solution: Rewrite each description to be 10-20 words, factual, and value-oriented. Good: `Complete REST API reference covering authentication, rate limiting, and all 47 endpoints`. Bad: `API documentation`.

### Issue: Using llms.txt as a sitemap replacement

Cause: Misunderstanding the standard's purpose -- llms.txt is for curation, not exhaustive indexing.
Solution: llms.txt coexists with sitemap.xml. The sitemap lists every indexable page; llms.txt lists only the pages most useful for LLM consumption. Remove pages that are not useful for AI context (login, admin, legal boilerplate, duplicate content).
