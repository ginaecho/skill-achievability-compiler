# ce_sources: public agent-skill corpus

294 real, publicly available `SKILL.md` agent-skill documents, each stored verbatim
(byte-identical to upstream) at `<id>/SKILL.md` next to the license that covers it (`<id>/LICENSE`).
Provenance is in `sources.json`: one record per skill with `id`, `repo_url`, `commit`, `path_in_repo`,
`license_spdx`, `license_file` (path of the copied license inside the upstream repo), `sha256`,
`bytes` and a short `domain` label. Records are sorted by `id`; `id` is
`<org>__<repo>__<skill-dir>`, lower-cased and reduced to `[a-z0-9_-]`.

Collected on 2026-09-26 with `git clone --depth 1` of each repository's default branch; the commit
recorded is `git rev-parse HEAD` of that clone.

## Selection rules

1. Candidates: every file named `SKILL.md` in the cloned repositories (skipping `.git/` and `node_modules/`).
   Symlinks are resolved and the real file contents are used.
2. License: the nearest `LICENSE`/`LICENSE.txt`/`COPYING` file, searching the skill directory first and then
   each parent directory up to the repository root. A stub license file that only points to the root
   LICENSE (getsentry `django-perf-review`) is replaced by the root file. Only skills under a license that
   permits redistribution were kept (MIT, Apache-2.0, MPL-2.0, CC-BY-SA-4.0). Excluded: Anthropic's
   source-available document skills (docx, pdf, pptx, xlsx: "All rights reserved"), the Figma skills in
   openai/skills (Figma Developer Terms), and skills with no license file at all (vercel-labs/agent-skills,
   whose README says MIT but which ships no LICENSE file; anthropics/skills `doc-coauthoring` and `template`).
3. Size: 300 bytes <= SKILL.md <= 60 KB.
4. Paths under `template(s)/`, `test(s)/`, `fixtures/` or `evals/` directories are skipped (scaffolds and test fixtures).
5. Duplicates: exact duplicates (same sha256) are dropped, as are near-duplicates (5-word-shingle Jaccard > 0.6,
   or > 0.25 with the same skill directory name). Repositories are processed in a fixed order that
   prefers the original publisher (e.g. anthropics/skills before microsoft/skills and github/awesome-copilot),
   so the earliest copy is kept.
6. Disjointness: the 8 skills of `benchmark/compaction_sources` are excluded (by repo+path, sha256, and
   same-repo skill name, which also removes their symlinked plugin copies).
7. Caps: the three large collections (microsoft/skills, github/awesome-copilot, trailofbits/skills) are capped
   at 30 skills each. Within those repos, skills are grouped by the first hyphen token of their directory
   name (e.g. `azure`, `wiki`, `trailmark`) and drawn round-robin across groups in a fixed sha256-based
   order, so no single SDK family fills the quota. All other repositories contribute all eligible skills.
8. `domain` is a hand-assigned short category label based on each skill's name and description.

## Counts

Total: **294** skills from **15** repositories.

### Per repository

| repository | commit | selected |
|---|---|---:|
| openai/skills | `49f948faa9258a0c61caceaf225e179651397431` | 35 |
| github/awesome-copilot | `6c4d33b9cfca967a28bb2962ef4d55e4a384c88c` | 30 |
| microsoft/skills | `23d0dac5f83f268166a17f0bc7dc6c73dc348a33` | 30 |
| trailofbits/skills | `0cc1c73a5e96749ab32d7ea5e14892fafa6972ae` | 30 |
| getsentry/skills | `c2f99a5b04b4cd992ec3022d7c2c3e23e938d241` | 27 |
| expo/skills | `efa52f0a9d2176db75992736281c77da1b714fa3` | 26 |
| huggingface/skills | `80f9fa530e46f4ae642fcb9e1725bad0e1979395` | 25 |
| hashicorp/agent-skills | `516354c484b43fa5469567485113dd0c769c3d24` | 20 |
| obra/superpowers | `8ca22dba9a94f28898bbce59f2537ff4d87c747d` | 15 |
| cloudflare/skills | `6dc7604903127485e7e4cb26314651ebd4a4df19` | 14 |
| anthropics/skills | `33375500bcea98d610eb30ce10ac4e59b89c390d` | 13 |
| cli/cli | `9b031151a825bda919203c5202876a725d637368` | 13 |
| neondatabase/agent-skills | `80164a28443aca7c82ac1a70aed836950d6c29ea` | 8 |
| microsoft/aspire-skills | `a83ca78b9d35b8238f9c4fdba72cb779defe2a90` | 6 |
| supabase/agent-skills | `551274ed2fe97c8fea1325f7ceb05803a542f8df` | 2 |

### Per license

| license (SPDX) | count |
|---|---:|
| MIT | 126 |
| Apache-2.0 | 117 |
| CC-BY-SA-4.0 | 31 |
| MPL-2.0 | 20 |

CC-BY-SA-4.0 content (all trailofbits/skills entries and getsentry `security-review`) is share-alike:
redistribution of these files and adaptations must keep that license and attribution.

### Per domain

| domain | count |
|---|---:|
| cloud-devops | 52 |
| ai-agents-llm | 45 |
| security | 35 |
| mobile | 26 |
| data-ml | 24 |
| dev-workflow-git | 23 |
| testing-qa | 23 |
| design-frontend | 15 |
| docs-writing | 12 |
| productivity-comms | 12 |
| databases | 9 |
| software-engineering | 7 |
| observability | 6 |
| media-audio-docs | 5 |

### Exclusions (candidates not selected)

| reason | count |
|---|---:|
| repo cap (30) not selected | 626 |
| exact duplicate (sha256) | 14 |
| license:NONE | 11 |
| in compaction_sources | 10 |
| license:PROPRIETARY-Figma | 8 |
| near-duplicate (5-gram Jaccard) of an earlier-kept skill | 8 |
| license:PROPRIETARY-Anthropic | 4 |
| size>60KB | 3 |
| template/test/eval-fixture path | 3 |

Repositories tried that could not be used: `stripe/agent-skills` (clone failed: GitHub asked for credentials,
i.e. the repository does not exist publicly); `vercel-labs/agent-skills` cloned but has no LICENSE file.
`google/langextract` contributed nothing new (its only skill is already in `compaction_sources`).
