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


## Batch 2: additional external skills (80-120 growth pass)

Total NEW files checked: 117 (fetched 2026-09-02 from 8 additional repos; see PROVENANCE.json). Checked with `skillc check --profile claude-ai` and `skillc check --profile no-shell` as specified.

| File | claude-ai verdict | claude-ai missing | no-shell verdict | no-shell missing |
|---|---|---|---|---|
| `real-skills-ext/lgbarn__devops-skills/aws-profile-management/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/lgbarn__devops-skills/terraform-drift-detection/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/lgbarn__devops-skills/terraform-plan-review/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/lgbarn__devops-skills/terraform-state-operations/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/lgbarn__devops-skills/historical-pattern-analysis/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/lgbarn__devops-skills/provider-upgrade-analysis/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/lgbarn__devops-skills/auto-documentation/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/lgbarn__devops-skills/using-devops-skills/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/lgbarn__devops-skills/dispatching-parallel-agents/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/01-recon-osint/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | cloud_enum | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/02-vulnerability-scanner/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/03-exploit-development/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/04-reverse-engineering/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/05-malware-analysis/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/06-threat-hunting/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/07-incident-response/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/09-web-security/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/10-cloud-security/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/14-red-team-ops/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/16-ai-llm-security/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/19-grc-compliance/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/wondelai__skills/jobs-to-be-done/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/lean-startup/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/lean-analytics/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/domain-driven-design/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/wondelai__skills/clean-architecture/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/design-sprint/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/high-output-management/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/mom-test/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/cro-methodology/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/contagious/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/blue-ocean-strategy/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/crossing-the-chasm/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/inspired-product/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/monetizing-innovation/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/wondelai__skills/hundred-million-offers/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/rust-engineer/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Jeffallan__claude-skills/golang-pro/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Jeffallan__claude-skills/kotlin-specialist/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Jeffallan__claude-skills/swift-expert/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/flutter-expert/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Jeffallan__claude-skills/terraform-engineer/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/kubernetes-specialist/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Jeffallan__claude-skills/sre-engineer/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Jeffallan__claude-skills/chaos-engineer/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Jeffallan__claude-skills/database-optimizer/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Jeffallan__claude-skills/graphql-architect/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/mcp-developer/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/prompt-engineer/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/rag-architect/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/secure-code-guardian/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/test-master/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/playwright-expert/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/Jeffallan__claude-skills/ml-pipeline/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/azure-cost/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/azure-compliance/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/azure-kubernetes/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/microsoft__skills/azure-diagnostics/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/microsoft__skills/entra-app-registration/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/kql/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/mcp-builder/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/microsoft-docs/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/microsoft__skills/podcast-generation/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/skill-creator/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | azure_core | IMPOSSIBLE [MISSING_CAPABILITY] | azure_core |
| `real-skills-ext/microsoft__skills/frontend-design-review/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/cloud-solution-architect/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/continual-learning/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/microsoft__skills/github-issue-creator/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/wiki-architect/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/wiki-qa/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/microsoft__skills/declarative-agent-developer/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/microsoft__skills/teams-app-developer/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/microsoft__skills/ui-widget-developer/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/microsoft__skills/azure-identity-dotnet/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/microsoft__skills/azure-ai-ml-py/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/jupyter-notebook/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/security-threat-model/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/openai__skills/security-best-practices/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/openai__skills/security-ownership-map/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/sentry/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/playwright/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/cli-creator/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/define-goal/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | create_goal | IMPOSSIBLE [MISSING_CAPABILITY] | create_goal |
| `real-skills-ext/openai__skills/cloudflare-deploy/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/vercel-deploy/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/figma-implement-design/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | get_design_context | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/figma-generate-design/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | generate_figma_design | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/notion-meeting-intelligence/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/openai__skills/gh-fix-ci/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/winui-app/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/imagegen/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | image_gen | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/openai__skills/plugin-creator/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Security-Phoenix-demo__security-skills-claude-code/cti-search-skill/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Security-Phoenix-demo__security-skills-claude-code/notebooklm/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Security-Phoenix-demo__security-skills-claude-code/opengrep-rule-generator/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/Security-Phoenix-demo__security-skills-claude-code/secure-prd-skill/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | present_files |
| `real-skills-ext/glebis__claude-skills/pdf-generation/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/tufte-report/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/typography/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/i18n-studio/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/design-tokens/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/glebis__claude-skills/nielsen-heuristics/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/glebis__claude-skills/rigorous-experiments/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/rag-eval/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/deep-research/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/firecrawl-research/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/meeting-prep/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | get_booking_attendees | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/weekly-digest/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | lookback_days | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/retrospective/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/tdd/SKILL.md` | IMPOSSIBLE [MISSING_CAPABILITY] | old_code | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/decision-toolkit/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/glebis__claude-skills/jtbd/SKILL.md` | ACHIEVABLE | - | ACHIEVABLE | - |
| `real-skills-ext/glebis__claude-skills/presentation-generator/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/whitepaper-audit/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/youtube-transcript/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/repo-publish/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |
| `real-skills-ext/glebis__claude-skills/skill-studio/SKILL.md` | ACHIEVABLE | - | IMPOSSIBLE [MISSING_CAPABILITY] | bash |

**Summary for this batch:** claude-ai: 108 ACHIEVABLE / 9 IMPOSSIBLE. no-shell: 43 ACHIEVABLE / 74 IMPOSSIBLE. **65 of 117 skills flip verdict** between the two profiles (almost all because the skill body invokes `bash` — a tool present in `claude-ai` but absent from `no-shell` — without declaring it in its own frontmatter). No `skillc check` errors were encountered on any of the 117 new files.

