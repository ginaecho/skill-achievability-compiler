# Tokens with the checker and without it

162 real skills. The deterministic check spends **no model tokens**; median 11.9 ms per skill, 2134 ms for the corpus.

## When is an LLM needed?

The escalation detector (`skillc autocheck`) fires on **130 of 162** skills (80.2%): the document carries completion language, guards or irreversible verbs that the deterministic reader could not turn into a pack, and the deterministic verdict is a CERTIFICATION, which the weak reading cannot support. The other 32 are settled for free. In the file-only runtime the picture inverts: 108 skills are REFUTED, and a refutation on the weak reading is sound whatever the document means, so only 49 escalate there. 0 skills took the semantic path.

## What escalation costs (measured)

| | value |
|---|---|
| compactions measured (haiku) | 20 |
| median tokens per compaction | 22440 |
| median USD per compaction | 0.08793 |
| tokens per input character | 2.991 |
| estimate for unmeasured skills | 17939 + 0.595 x chars |

## Against what an agent run costs

| | value |
|---|---|
| measured agent runs (usefulness experiment) | 134 |
| median tokens per run | 80331 |
| median USD per run | 0.0548 |
| median turns per run | 6 |
| tokens spent on runs the checker refuted and that failed | 15841106 |
| USD on those runs | 14.296 |

## The comparison

Two regimes, and they are not close.

**Where the check is free** (32 of 162 skills, including all 108 refutations in the file-only runtime): the check costs **0 model tokens** and 11.9 ms. Each refutation replaces an agent run whose measured median is 80331 tokens ($0.0548). In the usefulness experiment the runs the checker refuted and that then failed cost 15841106 tokens ($14.296) --- the checker would have spent none of it.

**Where the check needs an LLM** (130 skills in the home runtime, where the deterministic pack can only certify weakly): one compaction costs a median 22440 tokens, i.e. **27.9%** of one measured agent run (0.28 runs). It is paid once per skill version and amortizes over every run of that skill; against the per-skill runtime estimate the corpus share is 44.5% (median 54.463%).

## Per skill

| skill | home | no-shell | escalate | compaction tokens | est. run tokens | check share |
|---|---|---|---|---|---|---|
| `real-skills/skills/claude-api/SKILL.md` | ok | MISSING_CAPABILITY | yes | 69182 | 162282 | 42.631% |
| `real-skills/skills/skill-creator/SKILL.md` | ok | MISSING_CAPABILITY | yes | 36948 | 79086 | 46.719% |
| `real-skills-ext/obra__superpowers/writing-skills/SKILL.md` | ok | MISSING_CAPABILITY | yes | 33558 (est) | 68466 | 49.014% |
| `real-skills/skills/xlsx/SKILL.md` | ok | MISSING_CAPABILITY | yes | 32028 | 40488 | 79.105% |
| `real-skills-ext/microsoft__skills/ui-widget-developer/SKILL.md` | ok | MISSING_CAPABILITY | yes | 31661 (est) | 63432 | 49.913% |
| `real-skills-ext/alirezarezvani__claude-skills/terraform-patterns/SKILL.md` | ok | MISSING_CAPABILITY | yes | 30781 (est) | 61092 | 50.385% |
| `real-skills-ext/wondelai__skills/monetizing-innovation/SKILL.md` | ok | ok | yes | 30391 (est) | 60060 | 50.601% |
| `real-skills/skills/pptx/SKILL.md` | ok | MISSING_CAPABILITY | yes | 30220 (est) | 59604 | 50.701% |
| `real-skills-ext/wondelai__skills/high-output-management/SKILL.md` | ok | ok | yes | 30155 (est) | 59430 | 50.74% |
| `real-skills-ext/wondelai__skills/hundred-million-offers/SKILL.md` | ok | ok | yes | 29791 (est) | 58464 | 50.956% |
| `real-skills/skills/algorithmic-art/SKILL.md` | ok | ok | yes | 29677 (est) | 58164 | 51.023% |
| `real-skills/skills/doc-coauthoring/SKILL.md` | ok | ok | yes | 29182 | 51972 | 56.149% |
| `real-skills-ext/microsoft__skills/kql/SKILL.md` | ok | ok | yes | 29155 (est) | 56778 | 51.349% |
| `real-skills-ext/wondelai__skills/contagious/SKILL.md` | ok | ok | yes | 28423 (est) | 54834 | 51.835% |
| `real-skills-ext/microsoft__skills/cloud-solution-architect/SKILL.md` | ok | ok | yes | 28314 (est) | 54546 | 51.908% |
| `real-skills-ext/Security-Phoenix-demo__security-skills-claude-code/opengrep-rule-generator/SKILL.md` | ok | MISSING_CAPABILITY | yes | 28270 (est) | 54432 | 51.936% |
| `real-skills-ext/wondelai__skills/cro-methodology/SKILL.md` | ok | ok | yes | 28092 (est) | 53958 | 52.063% |
| `real-skills-ext/wondelai__skills/lean-startup/SKILL.md` | ok | ok | yes | 28031 (est) | 53796 | 52.106% |
| `real-skills-ext/wondelai__skills/lean-analytics/SKILL.md` | ok | ok | yes | 28015 (est) | 53748 | 52.123% |
| `real-skills-ext/wondelai__skills/mom-test/SKILL.md` | ok | ok | yes | 27942 (est) | 53556 | 52.173% |
| `real-skills-ext/wondelai__skills/jobs-to-be-done/SKILL.md` | ok | ok | yes | 27749 (est) | 53046 | 52.311% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/diffdock/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27660 (est) | 52806 | 52.38% |
| `real-skills-ext/wondelai__skills/clean-architecture/SKILL.md` | ok | ok | yes | 27637 (est) | 52746 | 52.396% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/10-cloud-security/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27627 (est) | 52722 | 52.401% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/biopython/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27506 (est) | 52398 | 52.494% |
| `real-skills-ext/wondelai__skills/inspired-product/SKILL.md` | ok | ok | yes | 27372 (est) | 52044 | 52.594% |
| `real-skills-ext/wondelai__skills/domain-driven-design/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27092 (est) | 51300 | 52.811% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/deeptools/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27051 (est) | 51192 | 52.842% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/14-red-team-ops/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27024 (est) | 51120 | 52.864% |
| `real-skills-ext/wondelai__skills/design-sprint/SKILL.md` | ok | ok | yes | 27017 (est) | 51102 | 52.869% |
| `real-skills-ext/Jeffallan__claude-skills/flutter-expert/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26973 | 35868 | 75.201% |
| `real-skills-ext/alirezarezvani__claude-skills/helm-chart-builder/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26877 (est) | 50730 | 52.98% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/07-incident-response/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26783 (est) | 50478 | 53.059% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/09-web-security/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26693 (est) | 50244 | 53.127% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/05-malware-analysis/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26664 (est) | 50166 | 53.152% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26596 (est) | 49986 | 53.207% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/cobrapy/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26550 (est) | 49860 | 53.249% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/astropy/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26545 (est) | 49848 | 53.252% |
| `real-skills-ext/wondelai__skills/crossing-the-chasm/SKILL.md` | ok | ok | yes | 26543 (est) | 49842 | 53.254% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/generate-image/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26525 (est) | 49794 | 53.269% |
