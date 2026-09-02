# Is the checker useful? Real skills, real agents, two runtimes

16 skills/tasks, 96 agent runs, models ['haiku', 'sonnet'].

## Aggregate

| | refuted by the checker | certified by the checker |
|---|---|---|
| configurations (skill × runtime) | 12 | 12 |
| agent runs | 48 | 48 |
| success (verified) | 20 | 45 |
| silent wrong (claims done, fails verification) | 2 | 0 |
| honest failure | 24 | 0 |
| agent cost (USD) | 2.38 | 2.334 |
| agent tokens | 2778884 | — |
| checker time, all configurations | 165.3 ms | |

## Per model

| model | refuted runs | silent wrong | honest fail | success | cost | certified runs | success | silent wrong | cost |
|---|---|---|---|---|---|---|---|---|---|
| haiku | 24 | 2 | 10 | 10 | $1.09 | 24 | 23 | 0 | $0.763 |
| sonnet | 24 | 0 | 14 | 10 | $1.289 | 24 | 22 | 0 | $1.57 |

## Per skill and runtime

| skill | runtime | checker (ms) | runs | success | silent wrong | honest fail | no status | cost | tokens |
|---|---|---|---|---|---|---|---|---|---|
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | shell | certified (26.0) | 4 | 4 | 0 | 0 | 0 | $0.244 | 385439 |
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (4.9) | 4 | 4 | 0 | 0 | 0 | $0.271 | 357674 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | shell | certified (8.0) | 4 | 4 | 0 | 0 | 0 | $0.206 | 308418 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.1) | 4 | 4 | 0 | 0 | 0 | $0.269 | 259110 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | shell | certified (17.1) | 4 | 4 | 0 | 0 | 0 | $0.205 | 337926 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.5) | 4 | 4 | 0 | 0 | 0 | $0.191 | 191829 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | shell | certified (11.0) | 4 | 4 | 0 | 0 | 0 | $0.179 | 224384 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (4.5) | 4 | 4 | 0 | 0 | 0 | $0.184 | 164816 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | shell | certified (11.8) | 4 | 4 | 0 | 0 | 0 | $0.296 | 363291 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (7.7) | 4 | 4 | 0 | 0 | 0 | $0.378 | 248727 |
| real-skills/skills/pdf/SKILL.md | shell | certified (6.2) | 4 | 4 | 0 | 0 | 0 | $0.144 | 242314 |
| real-skills/skills/pdf/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (2.3) | 4 | 0 | 0 | 4 | 0 | $0.208 | 157454 |
| real-skills/skills/xlsx/SKILL.md | shell | certified (8.2) | 4 | 2 | 0 | 0 | 2 | $0.3 | 581727 |
| real-skills/skills/xlsx/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.8) | 4 | 0 | 0 | 4 | 0 | $0.228 | 209766 |
| real-skills/skills/docx/SKILL.md | shell | certified (7.6) | 4 | 3 | 0 | 0 | 1 | $0.257 | 583559 |
| real-skills/skills/docx/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (2.9) | 4 | 0 | 0 | 4 | 0 | $0.182 | 121589 |
| benchmarks/spec-cases/order-in-budget/A/SKILL.md | shell | certified (9.6) | 4 | 4 | 0 | 0 | 0 | $0.094 | 210329 |
| benchmarks/spec-cases/publish-with-approval/A/SKILL.md | shell | certified (5.0) | 4 | 4 | 0 | 0 | 0 | $0.122 | 304949 |
| benchmarks/spec-cases/onboard-badge/A/SKILL.md | shell | certified (4.2) | 4 | 4 | 0 | 0 | 0 | $0.114 | 290417 |
| benchmarks/spec-cases/ledger-verify/A/SKILL.md | shell | certified (3.2) | 4 | 4 | 0 | 0 | 0 | $0.173 | 334143 |
| benchmarks/spec-cases/order-in-budget/B/SKILL.md | shell | refuted:GOAL_UNSAT (8.2) | 4 | 0 | 0 | 4 | 0 | $0.08 | 130090 |
| benchmarks/spec-cases/publish-with-approval/B/SKILL.md | shell | refuted:BLOCKED_GUARD (3.4) | 4 | 0 | 2 | 2 | 0 | $0.127 | 301949 |
| benchmarks/spec-cases/onboard-badge/B/SKILL.md | shell | refuted:GOAL_UNSAT (1.8) | 4 | 0 | 0 | 4 | 0 | $0.122 | 279752 |
| benchmarks/spec-cases/ledger-verify/B/SKILL.md | shell | refuted:MISSING_CAPABILITY (1.3) | 4 | 0 | 0 | 2 | 2 | $0.14 | 356128 |
