# Tokens with the checker and without it

157 real skills. The deterministic check spends **no model tokens**; median 32.3 ms per skill, 6025 ms for the corpus.

## When is an LLM needed?

The escalation detector (`skillc autocheck`) fires on **126 of 157** skills (80.3%): the document carries completion language, guards or irreversible verbs that the deterministic reader could not turn into a pack, and the deterministic verdict is a CERTIFICATION, which the weak reading cannot support. The other 31 are settled for free. In the file-only runtime the picture inverts: 103 skills are REFUTED, and a refutation on the weak reading is sound whatever the document means, so only 50 escalate there. 0 skills took the semantic path.

## What escalation costs (measured)

| | value |
|---|---|
| compactions measured (haiku) | 0 |
| median tokens per compaction | None |
| median USD per compaction | None |
| tokens per input character | None |

## Against what an agent run costs

| | value |
|---|---|
| measured agent runs (usefulness experiment) | 0 |
| median tokens per run | 0 |
| median USD per run | 0 |
| median turns per run | 0 |
| tokens spent on runs the checker refuted and that failed | 0 |
| USD on those runs | 0 |

Check as a share of one run: **0.0%** of corpus runtime tokens (median per skill 0.0%); on the 31 skills that need no LLM the share is 0.

## Per skill

| skill | home | no-shell | escalate | compaction tokens | est. run tokens | check share |
|---|---|---|---|---|---|---|
| `real-skills/skills/algorithmic-art/SKILL.md` | ok | ok | yes | 0 | 58164 | 0.0% |
| `real-skills/skills/brand-guidelines/SKILL.md` | ok | ok | no | 0 | 30534 | 0.0% |
| `real-skills/skills/canvas-design/SKILL.md` | ok | ok | yes | 0 | 45852 | 0.0% |
| `real-skills/skills/claude-api/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 192978 | 0.0% |
| `real-skills/skills/doc-coauthoring/SKILL.md` | ok | ok | yes | 0 | 51972 | 0.0% |
| `real-skills/skills/docx/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 37848 | 0.0% |
| `real-skills/skills/frontend-design/SKILL.md` | ok | ok | yes | 0 | 41784 | 0.0% |
| `real-skills/skills/internal-comms/SKILL.md` | ok | ok | yes | 0 | 29388 | 0.0% |
| `real-skills/skills/mcp-builder/SKILL.md` | ok | ok | yes | 0 | 44514 | 0.0% |
| `real-skills/skills/pdf/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 39690 | 0.0% |
| `real-skills/skills/pptx/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 59604 | 0.0% |
| `real-skills/skills/skill-creator/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 79086 | 0.0% |
| `real-skills/skills/slack-gif-creator/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 39384 | 0.0% |
| `real-skills/skills/theme-factory/SKILL.md` | ok | ok | yes | 0 | 31938 | 0.0% |
| `real-skills/skills/web-artifacts-builder/SKILL.md` | ok | MISSING_CAPABILITY | no | 0 | 31854 | 0.0% |
| `real-skills/skills/webapp-testing/SKILL.md` | ok | MISSING_CAPABILITY | no | 0 | 33102 | 0.0% |
| `real-skills/skills/xlsx/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 40488 | 0.0% |
| `real-skills-ext/ComposioHQ__awesome-claude-skills/brex-automation/SKILL.md` | ok | ok | yes | 0 | 31542 | 0.0% |
| `real-skills-ext/ComposioHQ__awesome-claude-skills/image-enhancer/SKILL.md` | ok | ok | yes | 0 | 30996 | 0.0% |
| `real-skills-ext/ComposioHQ__awesome-claude-skills/invoice-organizer/SKILL.md` | ok | ok | yes | 0 | 45348 | 0.0% |
| `real-skills-ext/ComposioHQ__awesome-claude-skills/langsmith-fetch/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 44046 | 0.0% |
| `real-skills-ext/ComposioHQ__awesome-claude-skills/video-downloader/SKILL.md` | ok | MISSING_CAPABILITY | no | 0 | 31218 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/chaos-engineer/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 38112 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/database-optimizer/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 36816 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/flutter-expert/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 36168 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/golang-pro/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 35208 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/graphql-architect/SKILL.md` | ok | ok | yes | 0 | 35316 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/kotlin-specialist/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 36630 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/kubernetes-specialist/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 40158 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/mcp-developer/SKILL.md` | ok | ok | yes | 0 | 36270 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/ml-pipeline/SKILL.md` | ok | ok | yes | 0 | 38694 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/playwright-expert/SKILL.md` | ok | ok | yes | 0 | 36054 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/prompt-engineer/SKILL.md` | ok | ok | yes | 0 | 36528 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/rag-architect/SKILL.md` | ok | ok | yes | 0 | 39690 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/rust-engineer/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 36750 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/secure-code-guardian/SKILL.md` | ok | ok | yes | 0 | 38364 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/sre-engineer/SKILL.md` | ok | MISSING_CAPABILITY | yes | 0 | 37926 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/swift-expert/SKILL.md` | ok | ok | yes | 0 | 36474 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/terraform-engineer/SKILL.md` | ok | ok | yes | 0 | 36090 | 0.0% |
| `real-skills-ext/Jeffallan__claude-skills/test-master/SKILL.md` | ok | ok | yes | 0 | 35190 | 0.0% |
