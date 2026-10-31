---
name: brand-scout
description: Scouts and secures your brand's digital presence — domain names, social media handles, and branding direction. Use when the user wants to find a name for a project, startup, product, or brand. Triggers on requests like "help me find a domain name", "brainstorm names for my project", "check if this domain is available", "I need a brand name", "scout social media handles", or any naming, domain, or brand research task.
---

# Brand Scout

A structured, human-in-the-loop workflow for finding the perfect brand name, securing domains, and claiming social media handles.

Before starting, load [references/brand-guide.xml](references/brand-guide.xml) — a comprehensive naming playbook covering 16 naming patterns, sound symbolism research, morpheme toolkits, domain strategy, case studies, and a 100-point scoring rubric. Reference it throughout the workflow.

## Workflow Overview

```
Discovery → Brainstorm + Score → Selection → Domain Check → Social Media → Report
    ↑                                |                            |
    └──────── Refine ────────────────┘                            |
                                     └──── Confirm domain ────────┘
```

Follow steps 1-7 in order. Steps 3-5 may loop until the user is satisfied.

## Step 1: Discovery

Ask the user about their project. Gather these essentials:

- **What** — Project description (1-2 sentences)
- **Who** — Target audience
- **Keywords** — 3-5 words that capture the essence
- **Vibe** — Professional, playful, technical, minimal, bold?
- **Industry** — Sector (tech, fintech, health, consumer, etc.)
- **Constraints** — Must-have TLD? Max length? Specific letters to avoid?

Keep discovery concise: 3-5 questions max in one message.

After discovery, identify the target brand attributes (speed, trust, innovation, simplicity, power, friendliness) — these drive sound recipe selection in Step 2.

## Step 2: Brainstorm

Generate 15-20 brand name candidates. Apply the naming patterns and linguistic techniques from the brand guide systematically.

**Use these naming patterns** (see `<naming_patterns>` in brand-guide.xml for full details):

| Pattern | Example | Trademark Strength |
|---------|---------|-------------------|
| Invented/Coined | Xerox, Hulu | Strongest (fanciful) |
| Real-word repurposed | Stripe, Slack, Notion | Strong (arbitrary) |
| Metaphorical | Amazon, Apple | Strong (suggestive) |
| Compound | Snapchat, Airtable | Moderate-strong |
| Portmanteau | Pinterest, Netflix | Strong |
| Suffix-modified | Spotify, Shopify | Strong |
| Misspelled/altered | Lyft, Tumblr | Moderate-strong |
| Foreign word | Uber, Lego | Strong |
| Personification | Alexa, Siri | Moderate |

**Apply sound symbolism** (see `<sound_recipes>` in brand-guide.xml):
- Map the user's desired brand attributes (speed, trust, innovation, etc.) to specific phoneme families
- Use front vowels (/i/, /e/) for lightness/speed; back vowels (/u/, /o/) for power/warmth
- Use plosives (p, t, k, b, d, g) for strength; fricatives (f, s, sh) for smoothness
- Target CVCV or CVC syllable patterns (the most universally pronounceable)
- Check phonaesthemes: gl- (light/vision), sw- (smooth movement), cr- (power)

**Use the morpheme toolkit** (see `<morpheme_toolkit>` in brand-guide.xml):
- Tech prefixes: Neo-, Hyper-, Omni-, Pro-, Re-, Inter-
- Popular suffixes: -er (89 startups), -ly (37), -ify, -io, -base, -hub, -flow
- Latin/Greek roots: nov- (new), lux- (light), ver- (truth), opt- (best), flex- (bend)

**Apply blending rules** for portmanteaus:
- Preserve each word's stressed syllable
- Target 2-3 syllable results
- Ensure both source words remain recognizable

Present names grouped by pattern with brief rationale for each. Note the trademark strength category (fanciful > arbitrary > suggestive > descriptive) for every candidate.

## Step 3: Score Names

### Automated Scoring

Run the name scorer on brainstormed candidates:

```bash
scripts/score_names.py name1 name2 name3 ...
```

To check for phonetic conflicts with competitors:
```bash
scripts/score_names.py name1 name2 --compare competitor1 competitor2
```

The scorer evaluates: length, syllable count, pronounceability, and phonetic fingerprint (Metaphone/Soundex). Scores range 0-1 with higher being better.

### Qualitative Evaluation

Supplement the automated scores with the 100-point rubric from `<scoring_rubric>` in brand-guide.xml. Evaluate each top candidate on these weighted criteria:

| Criterion | Points | What to assess |
|-----------|--------|----------------|
| Memorability | 12 | Plosives, alliteration, rhythm, concrete imagery |
| Trademark strength | 12 | Fanciful (12), Arbitrary (9), Suggestive (6), Descriptive (3) |
| Pronounceability | 10 | Unambiguous globally (10), clear in English (7), needs explanation (4) |
| Cultural safety | 10 | Check across major languages for negative meanings |
| Spellability | 8 | Passes the radio test — hear once, spell correctly |
| Semantic resonance | 8 | Positive associations aligned to brand |
| Emotional impact | 8 | Sound symbolism matches brand personality |
| Competitive differentiation | 8 | Unique in category |
| Visual aesthetics | 5 | Balanced letterforms, works as wordmark |
| Length/brevity | 5 | 4-8 chars ideal (5pts), 9-11 (4pts), 12-15 (2pts) |
| Domain availability | 5 | Assessed in Step 5 |
| Social handles | 3 | Assessed in Step 6 |
| Scalability | 3 | Works for unlimited expansion |
| SEO viability | 3 | Unique in search results |

**Scoring tiers:** 85-100 exceptional → 70-84 strong → 55-69 viable → below 55 reject.

**Mandatory filters** (instant fail if not passed):
- **Radio test**: Can someone hear it once and type it into a browser?
- **Coffee shop test**: If you have to spell it out, the name fails.

Present a combined table: automated scores + qualitative rubric score + trademark category.

## Step 4: Selection

Present scored results and ask the user to:

1. Pick their top 5-8 favorites
2. Flag any names they want variations of
3. Indicate preferred TLDs (suggest .com + 1-2 relevant alternatives)

If the user wants more options, loop back to Step 2 with refined direction.

## Step 5: Domain Availability Check

Run the domain checker on selections:

```bash
scripts/check_domains.py name1 name2 ... --tlds com,io,dev,ai
```

For definitive results (slower, uses WHOIS):
```bash
scripts/check_domains.py name1 name2 ... --whois
```

**Status key:**
- `taken` — Registered (DNS or WHOIS confirmed)
- `AVAILABLE` — Unregistered (WHOIS confirmed)
- `possibly available` — DNS negative, not WHOIS-verified (use `--whois` to confirm)

**TLD selection** — Apply the decision tree from `<domain_strategy>` in brand-guide.xml:
1. Is exact brand.com available? → Take it immediately
2. AI startup? → .ai preferred, then .com
3. Dev tools/SaaS? → .io or .dev preferred, then .com
4. Consumer/mass market? → .com strongly preferred
5. None available? → Try verb prefixes (get/try/use) or modify the name itself

For additional TLD guidance, see [references/tld-guide.xml](references/tld-guide.xml).

If top choices are taken, suggest domain workarounds from the brand guide:
- Verb prefixes: get-, try-, use-, hey-, meet-, join-
- Suffixes: -hq, -app, -labs
- Domain hacks: notion.so, linear.app, bit.ly
- Note: Facebook launched as thefacebook.com, Dropbox as getdropbox.com — startups upgrade later

**Defensive registration**: Recommend securing the brand name across 3-5 key TLDs (.com, .io, .co, .ai, .net) to prevent squatters.

## Step 6: Social Media Handle Check

Once the user confirms a domain name, run the handle checker:

```bash
scripts/check_handles.py myhandle
```

Check all supported platforms:
```bash
scripts/check_handles.py myhandle --all
```

**Supported platforms:** github, twitter, instagram, linkedin, reddit_user, reddit_sub, youtube, tiktok, npm, pypi

If the exact handle is taken, suggest variations and re-check:
- Add "hq", "app", "official", "get", "use" as prefix/suffix
- Use underscores or periods where platforms allow

```bash
scripts/check_handles.py myhandlehq myhandle_app --platforms github,twitter,instagram
```

## Step 7: Final Report

Generate a comprehensive brand research report. Draw on the case studies and trends from brand-guide.xml to provide informed branding context.

```markdown
# Brand Scout Report: [chosen name]

## Name Analysis

| Metric | Value |
|--------|-------|
| Pattern | [naming pattern used, e.g., "real-word repurposed"] |
| Trademark category | [fanciful/arbitrary/suggestive/descriptive] |
| Syllables | [count] |
| Pronounceability | [score] |
| Phonetic code | [metaphone] |
| Rubric score | [X/100] |

## Sound Profile

- **Phoneme analysis**: [e.g., "voiceless fricatives + front vowels convey speed"]
- **Syllable pattern**: [e.g., CVC — punchy monosyllable]
- **Sound associations**: [what the name's sounds convey per sound symbolism]

## Domain Availability

| Domain | Status | Action |
|--------|--------|--------|
| name.com | Available | Register immediately |
| name.io | Taken | — |

**Recommended TLD**: [primary recommendation with reasoning]
**Defensive registrations**: [3-5 TLDs to secure]

## Social Media Handles

| Platform | Handle | Status | Alternative |
|----------|--------|--------|-------------|
| GitHub | @name | Available | — |
| Twitter/X | @name | Taken | @namehq |

## Branding Direction

- **Pronunciation guide**: [phonetic spelling if non-obvious]
- **Tagline ideas**: [2-3 suggestions]
- **Visual direction**: [brief color/style notes informed by sound profile]
- **Tone**: [professional, playful, technical]
- **Comparable brands**: [1-2 similar successful names from case studies]

## Next Steps

1. Register domain at [registrar suggestion]
2. Secure social media handles (prioritized by platform importance)
3. Consider professional trademark search ($120K-$750K avg dispute cost)
4. Register defensive domains (.com variant if using alternative TLD)
5. Budget: $50-200 for defensive domain registration
```

Save the report to a markdown file in the user's working directory.
