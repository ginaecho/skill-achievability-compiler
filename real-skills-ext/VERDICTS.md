# skillc Verdicts on External Real-Skill Corpus

Total files checked: 28


| File | claude-ai verdict | none verdict | tools extracted (missing under `none`) |
|---|---|---|---|
| `ComposioHQ__awesome-claude-skills/brex-automation/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `ComposioHQ__awesome-claude-skills/image-enhancer/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `ComposioHQ__awesome-claude-skills/invoice-organizer/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `ComposioHQ__awesome-claude-skills/langsmith-fetch/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `ComposioHQ__awesome-claude-skills/video-downloader/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `K-Dense-AI__claude-scientific-skills/astropy/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `K-Dense-AI__claude-scientific-skills/bgpt-paper-search/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | IMPOSSIBLE [MISSING_CAPABILITY] | search_papers |
| `K-Dense-AI__claude-scientific-skills/biopython/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `K-Dense-AI__claude-scientific-skills/citation-management/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | IMPOSSIBLE [MISSING_CAPABILITY] | citation_doi |
| `K-Dense-AI__claude-scientific-skills/cobrapy/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `K-Dense-AI__claude-scientific-skills/dask/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | IMPOSSIBLE [MISSING_CAPABILITY] | bash, map_blocks, map_partitions |
| `K-Dense-AI__claude-scientific-skills/deeptools/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `K-Dense-AI__claude-scientific-skills/diffdock/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `K-Dense-AI__claude-scientific-skills/esm/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `K-Dense-AI__claude-scientific-skills/exa-search/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `K-Dense-AI__claude-scientific-skills/generate-image/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `alirezarezvani__claude-skills/data-quality-auditor/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `alirezarezvani__claude-skills/docker-development/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `alirezarezvani__claude-skills/feature-flags-architect/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `alirezarezvani__claude-skills/google-workspace-cli/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `alirezarezvani__claude-skills/helm-chart-builder/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `alirezarezvani__claude-skills/kubernetes-operator/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `alirezarezvani__claude-skills/playwright-pro-pw/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `alirezarezvani__claude-skills/snowflake-development/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | IMPOSSIBLE [MISSING_CAPABILITY] | bash, dynamic_table, snake_case |
| `alirezarezvani__claude-skills/terraform-patterns/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `obra__superpowers/using-git-worktrees/SKILL.md` | ACHIEVABLE | ACHIEVABLE | - |
| `obra__superpowers/writing-skills/SKILL.md` | ACHIEVABLE | IMPOSSIBLE [MISSING_CAPABILITY] | bash |

**10 of 28 skills flip verdict between profiles** (ACHIEVABLE under `claude-ai`, IMPOSSIBLE under `none`) — these are the skills whose bodies invoke concrete tools (chiefly `bash`) not declared in their own frontmatter, so achievability depends on which runtime capabilities are assumed.

**4 skills are IMPOSSIBLE under both profiles** (they invoke a capability that isn't a tool in either profile and isn't declared in their own frontmatter, e.g. an undeclared custom capability like `search_papers` or `citation_doi`):

- `K-Dense-AI__claude-scientific-skills/bgpt-paper-search/SKILL.md`: missing search_papers
- `K-Dense-AI__claude-scientific-skills/citation-management/SKILL.md`: missing citation_doi
- `K-Dense-AI__claude-scientific-skills/dask/SKILL.md`: missing map_blocks, map_partitions
- `alirezarezvani__claude-skills/snowflake-development/SKILL.md`: missing dynamic_table, snake_case

