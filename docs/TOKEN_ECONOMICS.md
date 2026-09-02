# Tokens with the checker and without it

162 real skills. The deterministic check spends **no model tokens**; median 10.0 ms per skill, 1813 ms for the corpus.

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
| measured agent runs (usefulness experiment) | 114 |
| median tokens per run | 72001 |
| median USD per run | 0.0489 |
| median turns per run | 5 |
| tokens spent on runs the checker refuted and that failed | 5098701 |
| USD on those runs | 4.259 |

## The comparison

Two regimes, and they are not close.

**Where the check is free** (32 of 162 skills, including all 108 refutations in the file-only runtime): the check costs **0 model tokens** and 10.0 ms. Each refutation replaces an agent run whose measured median is 72001 tokens ($0.0489). In the usefulness experiment the runs the checker refuted and that then failed cost 5098701 tokens ($4.259) --- the checker would have spent none of it.

**Where the check needs an LLM** (130 skills in the home runtime, where the deterministic pack can only certify weakly): one compaction costs a median 22440 tokens, i.e. **31.2%** of one measured agent run (0.31 runs). It is paid once per skill version and amortizes over every run of that skill; against the per-skill runtime estimate the corpus share is 56.076% (median 68.465%).

## Per skill

| skill | home | no-shell | escalate | compaction tokens | est. run tokens | check share |
|---|---|---|---|---|---|---|
| `real-skills/skills/claude-api/SKILL.md` | ok | MISSING_CAPABILITY | yes | 69182 | 133485 | 51.828% |
| `real-skills/skills/skill-creator/SKILL.md` | ok | MISSING_CAPABILITY | yes | 36948 | 64155 | 57.592% |
| `real-skills-ext/obra__superpowers/writing-skills/SKILL.md` | ok | MISSING_CAPABILITY | yes | 33558 (est) | 55305 | 60.678% |
| `real-skills/skills/xlsx/SKILL.md` | ok | MISSING_CAPABILITY | yes | 32028 | 31990 | 100.119% |
| `real-skills-ext/microsoft__skills/ui-widget-developer/SKILL.md` | ok | MISSING_CAPABILITY | yes | 31661 (est) | 51110 | 61.947% |
| `real-skills-ext/alirezarezvani__claude-skills/terraform-patterns/SKILL.md` | ok | MISSING_CAPABILITY | yes | 30781 (est) | 49160 | 62.614% |
| `real-skills-ext/wondelai__skills/monetizing-innovation/SKILL.md` | ok | ok | yes | 30391 (est) | 48300 | 62.921% |
| `real-skills/skills/pptx/SKILL.md` | ok | MISSING_CAPABILITY | yes | 30220 (est) | 47920 | 63.063% |
| `real-skills-ext/wondelai__skills/high-output-management/SKILL.md` | ok | ok | yes | 30155 (est) | 47775 | 63.119% |
| `real-skills-ext/wondelai__skills/hundred-million-offers/SKILL.md` | ok | ok | yes | 29791 (est) | 46970 | 63.426% |
| `real-skills/skills/algorithmic-art/SKILL.md` | ok | ok | yes | 29677 (est) | 46720 | 63.521% |
| `real-skills/skills/doc-coauthoring/SKILL.md` | ok | ok | yes | 29182 | 41560 | 70.217% |
| `real-skills-ext/microsoft__skills/kql/SKILL.md` | ok | ok | yes | 29155 (est) | 45565 | 63.986% |
| `real-skills-ext/wondelai__skills/contagious/SKILL.md` | ok | ok | yes | 28423 (est) | 43945 | 64.679% |
| `real-skills-ext/microsoft__skills/cloud-solution-architect/SKILL.md` | ok | ok | yes | 28314 (est) | 43705 | 64.784% |
| `real-skills-ext/Security-Phoenix-demo__security-skills-claude-code/opengrep-rule-generator/SKILL.md` | ok | MISSING_CAPABILITY | yes | 28270 (est) | 43610 | 64.825% |
| `real-skills-ext/wondelai__skills/cro-methodology/SKILL.md` | ok | ok | yes | 28092 (est) | 43215 | 65.005% |
| `real-skills-ext/wondelai__skills/lean-startup/SKILL.md` | ok | ok | yes | 28031 (est) | 43080 | 65.067% |
| `real-skills-ext/wondelai__skills/lean-analytics/SKILL.md` | ok | ok | yes | 28015 (est) | 43040 | 65.091% |
| `real-skills-ext/wondelai__skills/mom-test/SKILL.md` | ok | ok | yes | 27942 (est) | 42880 | 65.163% |
| `real-skills-ext/wondelai__skills/jobs-to-be-done/SKILL.md` | ok | ok | yes | 27749 (est) | 42455 | 65.361% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/diffdock/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27660 (est) | 42255 | 65.46% |
| `real-skills-ext/wondelai__skills/clean-architecture/SKILL.md` | ok | ok | yes | 27637 (est) | 42205 | 65.483% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/10-cloud-security/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27627 (est) | 42185 | 65.49% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/biopython/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27506 (est) | 41915 | 65.623% |
| `real-skills-ext/wondelai__skills/inspired-product/SKILL.md` | ok | ok | yes | 27372 (est) | 41620 | 65.766% |
| `real-skills-ext/wondelai__skills/domain-driven-design/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27092 (est) | 41000 | 66.078% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/deeptools/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27051 (est) | 40910 | 66.123% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/14-red-team-ops/SKILL.md` | ok | MISSING_CAPABILITY | yes | 27024 (est) | 40850 | 66.154% |
| `real-skills-ext/wondelai__skills/design-sprint/SKILL.md` | ok | ok | yes | 27017 (est) | 40835 | 66.161% |
| `real-skills-ext/Jeffallan__claude-skills/flutter-expert/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26973 | 28140 | 95.853% |
| `real-skills-ext/alirezarezvani__claude-skills/helm-chart-builder/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26877 (est) | 40525 | 66.322% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/07-incident-response/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26783 (est) | 40315 | 66.434% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/09-web-security/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26693 (est) | 40120 | 66.533% |
| `real-skills-ext/Masriyan__Claude-Code-CyberSecurity-Skill/05-malware-analysis/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26664 (est) | 40055 | 66.568% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26596 (est) | 39905 | 66.648% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/cobrapy/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26550 (est) | 39800 | 66.709% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/astropy/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26545 (est) | 39790 | 66.713% |
| `real-skills-ext/wondelai__skills/crossing-the-chasm/SKILL.md` | ok | ok | yes | 26543 (est) | 39785 | 66.716% |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/generate-image/SKILL.md` | ok | MISSING_CAPABILITY | yes | 26525 (est) | 39745 | 66.738% |
