# Is the checker useful? Real skills, real agents, two runtimes

21 skills/tasks, 136 agent runs, models ['haiku', 'sonnet'].

## Aggregate

| | refuted by the checker | certified by the checker |
|---|---|---|
| configurations (skill × runtime) | 15 | 19 |
| agent runs | 60 | 76 |
| success (verified) | 21 | 68 |
| silent wrong (claims done, fails verification) | 2 | 1 |
| honest failure | 37 | 7 |
| agent cost (USD) | 4.501 | 3.101 |
| agent tokens | 6398421 | — |
| checker time, all configurations | 564.4 ms | |

## Per model

| model | refuted runs | silent wrong | honest fail | success | cost | certified runs | success | silent wrong | cost |
|---|---|---|---|---|---|---|---|---|---|
| haiku | 30 | 2 | 18 | 10 | $0.597 | 38 | 33 | 1 | $0.268 |
| sonnet | 30 | 0 | 19 | 11 | $3.903 | 38 | 35 | 0 | $2.835 |

## Per skill and runtime

| skill | runtime | checker (ms) | runs | success | silent wrong | honest fail | no status | cost | tokens |
|---|---|---|---|---|---|---|---|---|---|
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | shell | certified (57.1) | 4 | 4 | 0 | 0 | 0 | $0.139 | 218748 |
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (7.5) | 4 | 4 | 0 | 0 | 0 | $0.121 | 162039 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | shell | certified (20.9) | 4 | 4 | 0 | 0 | 0 | $0.11 | 209463 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (4.7) | 4 | 4 | 0 | 0 | 0 | $0.086 | 126941 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | shell | certified (75.9) | 4 | 4 | 0 | 0 | 0 | $0.119 | 229935 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (5.4) | 4 | 4 | 0 | 0 | 0 | $0.096 | 136673 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | shell | certified (26.4) | 4 | 4 | 0 | 0 | 0 | $0.112 | 185201 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (5.6) | 4 | 4 | 0 | 0 | 0 | $0.091 | 128052 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | shell | certified (8.5) | 4 | 4 | 0 | 0 | 0 | $0.13 | 207791 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | no-shell | certified (8.3) | 4 | 4 | 0 | 0 | 0 | $0.119 | 156141 |
| real-skills/skills/pdf/SKILL.md | shell | certified (16.1) | 4 | 3 | 0 | 1 | 0 | $0.098 | 207129 |
| real-skills/skills/pdf/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.6) | 4 | 0 | 0 | 4 | 0 | $0.102 | 87746 |
| real-skills/skills/xlsx/SKILL.md | shell | certified (14.9) | 4 | 4 | 0 | 0 | 0 | $0.118 | 301966 |
| real-skills/skills/xlsx/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (5.2) | 4 | 0 | 0 | 4 | 0 | $0.061 | 46490 |
| real-skills/skills/docx/SKILL.md | shell | certified (19.7) | 4 | 4 | 0 | 0 | 0 | $0.091 | 322968 |
| real-skills/skills/docx/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (4.3) | 4 | 0 | 0 | 4 | 0 | $0.058 | 67520 |
| benchmarks/spec-cases/order-in-budget/A/SKILL.md | shell | certified (23.2) | 4 | 4 | 0 | 0 | 0 | $0.061 | 132743 |
| benchmarks/spec-cases/publish-with-approval/A/SKILL.md | shell | certified (13.0) | 4 | 3 | 0 | 1 | 0 | $0.065 | 157333 |
| benchmarks/spec-cases/onboard-badge/A/SKILL.md | shell | certified (10.8) | 4 | 4 | 0 | 0 | 0 | $0.056 | 120292 |
| benchmarks/spec-cases/ledger-verify/A/SKILL.md | shell | certified (9.4) | 4 | 0 | 0 | 4 | 0 | $0.084 | 143526 |
| benchmarks/spec-cases/order-in-budget/B/SKILL.md | shell | refuted:GOAL_UNSAT (13.7) | 4 | 0 | 0 | 4 | 0 | $0.055 | 82285 |
| benchmarks/spec-cases/publish-with-approval/B/SKILL.md | shell | refuted:BLOCKED_GUARD (6.1) | 4 | 0 | 0 | 4 | 0 | $0.065 | 148125 |
| benchmarks/spec-cases/onboard-badge/B/SKILL.md | shell | refuted:GOAL_UNSAT (3.1) | 4 | 0 | 0 | 4 | 0 | $0.057 | 131180 |
| benchmarks/spec-cases/ledger-verify/B/SKILL.md | shell | refuted:MISSING_CAPABILITY (3.1) | 4 | 0 | 0 | 4 | 0 | $0.076 | 171919 |
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | shell | certified (29.9) | 4 | 4 | 0 | 0 | 0 | $0.141 | 275954 |
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (7.4) | 4 | 0 | 0 | 4 | 0 | $0.358 | 279984 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | shell | certified (20.6) | 4 | 4 | 0 | 0 | 0 | $0.11 | 208590 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (4.7) | 4 | 0 | 0 | 4 | 0 | $0.301 | 376407 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | shell | certified (76.7) | 4 | 4 | 0 | 0 | 0 | $0.14 | 408777 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (5.3) | 4 | 4 | 0 | 0 | 0 | $0.624 | 800121 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | shell | certified (29.9) | 4 | 4 | 0 | 0 | 0 | $0.138 | 452186 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (5.8) | 4 | 1 | 2 | 1 | 0 | $2.35 | 3652939 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | shell | certified (9.2) | 4 | 4 | 0 | 0 | 0 | $0.148 | 341108 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | no-shell | certified (8.4) | 4 | 2 | 1 | 1 | 0 | $1.122 | 1758645 |
