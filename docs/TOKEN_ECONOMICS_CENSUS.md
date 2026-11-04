# Tokens with the checker and without it

157 real skills. The deterministic check spends **no model tokens**; median 22.4 ms per skill, 4444 ms for the corpus.

## When is an LLM needed?

The escalation detector (`skillc autocheck`) fires on **126 of 157** skills (80.3%): the document carries completion language, guards or irreversible verbs that the deterministic reader could not turn into a pack, and the deterministic verdict is a CERTIFICATION, which the weak reading cannot support. The other 31 are settled for free. In the file-only runtime the picture inverts: 103 skills are REFUTED, and a refutation on the weak reading is sound whatever the document means, so only 50 escalate there. 0 skills took the semantic path.

## What escalation costs (measured)

| | value |
|---|---|
| compactions measured (haiku) | 20 |
| median tokens per compaction | 10711 |
| median USD per compaction | 0.00298 |
| tokens per input character | 1.208 |

## Against what an agent run costs

| | value |
|---|---|
| measured agent runs (usefulness experiment) | 136 |
| median tokens per run | 43051 |
| median USD per run | 0.0257 |
| median turns per run | 3 |
| tokens spent on runs the checker refuted and that failed | 4448525 |
| USD on those runs | 2.533 |

Check as a share of one run: **52.865%** of corpus runtime tokens (median per skill 54.753%); on the 31 skills that need no LLM the share is 0.

## Per skill

| skill | home | no-shell | escalate | compaction tokens | est. run tokens | check share |
|---|---|---|---|---|---|---|
| `real-skills/skills/claude-api/SKILL.md` | ok | MISSING_CAPABILITY | yes | 50949 | 93339 | 54.585% |
| `real-skills/skills/skill-creator/SKILL.md` | ok | MISSING_CAPABILITY | yes | 39860 (est) | 36393 | 109.527% |
| `real-skills-ext/microsoft__skills/ui-widget-developer/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27876 (est) | 28566 | 97.585% |
| `real-skills-ext/wondelai__skills/monetizing-innovation/SKILL.md` | ok | ok | yes | 25297 (est) | 26880 | 94.111% |
| `real-skills-ext/wondelai__skills/high-output-management/SKILL.md` | ok | ok | yes | 24817 (est) | 26565 | 93.42% |
| `real-skills-ext/wondelai__skills/hundred-million-offers/SKILL.md` | ok | ok | yes | 24078 (est) | 26082 | 92.317% |
| `real-skills-ext/microsoft__skills/kql/SKILL.md` | ok | ok | yes | 22786 (est) | 25239 | 90.281% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/deeptools/SKILL.md` | ok | MISSING_CAPABILITY | yes | 22106 (est) | 24795 | 89.155% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/generate-image/SKILL.md` | ok | MISSING_CAPABILITY | yes | 21539 (est) | 24423 | 88.191% |
| `real-skills-ext/wondelai__skills/contagious/SKILL.md` | ok | ok | yes | 21298 (est) | 24267 | 87.765% |
| `real-skills-ext/microsoft__skills/cloud-solution-architect/SKILL.md` | ok | ok | yes | 21078 (est) | 24123 | 87.377% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/10-cloud-security/SKILL.md` | ok | MISSING_CAPABILITY | yes | 20929 (est) | 24027 | 87.106% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/biopython/SKILL.md` | ok | MISSING_CAPABILITY | yes | 20805 (est) | 23946 | 86.883% |
| `real-skills-ext/wondelai__skills/cro-methodology/SKILL.md` | ok | ok | yes | 20626 (est) | 23829 | 86.558% |
| `real-skills-ext/wondelai__skills/lean-startup/SKILL.md` | ok | ok | yes | 20503 (est) | 23748 | 86.336% |
| `real-skills-ext/wondelai__skills/lean-analytics/SKILL.md` | ok | ok | yes | 20469 (est) | 23724 | 86.28% |
| `real-skills-ext/wondelai__skills/mom-test/SKILL.md` | ok | ok | yes | 20320 (est) | 23628 | 86.0% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md` | ok | MISSING_CAPABILITY | yes | 20283 (est) | 23604 | 85.93% |
| `real-skills-ext/obra__superpowers/writing-skills/SKILL.md` | ok | ok | yes | 20177 (est) | 23535 | 85.732% |
| `real-skills-ext/wondelai__skills/jobs-to-be-done/SKILL.md` | ok | ok | yes | 19929 (est) | 23373 | 85.265% |
| `real-skills-ext/wondelai__skills/clean-architecture/SKILL.md` | ok | ok | yes | 19702 (est) | 23223 | 84.838% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/14-red-team-ops/SKILL.md` | ok | MISSING_CAPABILITY | yes | 19696 (est) | 23220 | 84.823% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/07-incident-response/SKILL.md` | ok | MISSING_CAPABILITY | yes | 19220 (est) | 22908 | 83.901% |
| `real-skills-ext/wondelai__skills/inspired-product/SKILL.md` | ok | ok | yes | 19164 (est) | 22872 | 83.788% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/09-web-security/SKILL.md` | ok | MISSING_CAPABILITY | yes | 19032 (est) | 22785 | 83.529% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/05-malware-analysis/SKILL.md` | ok | MISSING_CAPABILITY | yes | 18985 (est) | 22755 | 83.432% |
| `real-skills-ext/wondelai__skills/domain-driven-design/SKILL.md` | ok | MISSING_CAPABILITY | yes | 18594 (est) | 22500 | 82.64% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/06-threat-hunting/SKILL.md` | ok | MISSING_CAPABILITY | yes | 18479 (est) | 22425 | 82.404% |
| `real-skills-ext/wondelai__skills/design-sprint/SKILL.md` | ok | ok | yes | 18443 (est) | 22401 | 82.331% |
| `real-skills-ext/alirezarezvani__claude-skills/helm-chart-builder/SKILL.md` | ok | MISSING_CAPABILITY | yes | 18311 (est) | 22314 | 82.061% |
| `real-skills-ext/wondelai__skills/crossing-the-chasm/SKILL.md` | ok | ok | yes | 17478 (est) | 21771 | 80.281% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/03-exploit-development/SKILL.md` | ok | MISSING_CAPABILITY | yes | 17466 (est) | 21762 | 80.259% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/04-reverse-engineering/SKILL.md` | ok | MISSING_CAPABILITY | yes | 17451 (est) | 21753 | 80.223% |
| `real-skills/skills/pptx/SKILL.md` | ok | MISSING_CAPABILITY | yes | 17372 | 26652 | 65.181% |
| `real-skills-ext/wondelai__skills/blue-ocean-strategy/SKILL.md` | ok | ok | yes | 16007 (est) | 20811 | 76.916% |
| `real-skills-ext/microsoft__skills/azure-kubernetes/SKILL.md` | ok | MISSING_CAPABILITY | yes | 15770 (est) | 20655 | 76.35% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/02-vulnerability-scanner/SKILL.md` | ok | MISSING_CAPABILITY | yes | 15585 (est) | 20535 | 75.895% |
| `real-skills-ext/microsoft__skills/declarative-agent-developer/SKILL.md` | ok | MISSING_CAPABILITY | yes | 15416 (est) | 20424 | 75.48% |
| `real-skills/skills/doc-coauthoring/SKILL.md` | ok | ok | yes | 15352 | 22836 | 67.227% |
| `real-skills-ext/glebis__claude-skills/deep-research/SKILL.md` | ok | MISSING_CAPABILITY | yes | 14987 (est) | 20142 | 74.407% |
