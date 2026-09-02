# Is the checker useful? Real skills, real agents, two runtimes

21 skills/tasks, 134 agent runs, models ['haiku', 'sonnet'].

## Aggregate

| | refuted by the checker | certified by the checker |
|---|---|---|
| configurations (skill × runtime) | 17 | 17 |
| agent runs | 66 | 68 |
| success (verified) | 20 | 64 |
| silent wrong (claims done, fails verification) | 7 | 1 |
| honest failure | 30 | 0 |
| agent cost (USD) | 15.59 | 3.979 |
| agent tokens | 17063262 | — |
| checker time, all configurations | 260.1 ms | |

## Per model

| model | refuted runs | silent wrong | honest fail | success | cost | certified runs | success | silent wrong | cost |
|---|---|---|---|---|---|---|---|---|---|---|
| haiku | 34 | 7 | 14 | 10 | $5.331 | 34 | 32 | 1 | $1.403 |
| sonnet | 32 | 0 | 16 | 10 | $10.258 | 34 | 32 | 0 | $2.576 |

## Per skill and runtime

| skill | runtime | checker (ms) | runs | success | silent wrong | honest fail | no status | timeout | cost | tokens |
|---|---|---|---|---|---|---|---|---|---|---|
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | shell | certified (21.9) | 4 | 4 | 0 | 0 | 0 | 0 | $0.244 | 385439 |
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.9) | 4 | 4 | 0 | 0 | 0 | 0 | $0.271 | 357674 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | shell | certified (7.5) | 4 | 4 | 0 | 0 | 0 | 0 | $0.206 | 308418 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (2.4) | 4 | 4 | 0 | 0 | 0 | 0 | $0.269 | 259110 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | shell | certified (14.4) | 4 | 4 | 0 | 0 | 0 | 0 | $0.205 | 337926 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (2.8) | 4 | 4 | 0 | 0 | 0 | 0 | $0.191 | 191829 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | shell | certified (9.7) | 4 | 4 | 0 | 0 | 0 | 0 | $0.179 | 224384 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.6) | 4 | 4 | 0 | 0 | 0 | 0 | $0.184 | 164816 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | shell | certified (9.9) | 4 | 4 | 0 | 0 | 0 | 0 | $0.296 | 363291 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (8.6) | 4 | 4 | 0 | 0 | 0 | 0 | $0.378 | 248727 |
| real-skills/skills/pdf/SKILL.md | shell | certified (7.9) | 4 | 4 | 0 | 0 | 0 | 0 | $0.144 | 242314 |
| real-skills/skills/pdf/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.1) | 4 | 0 | 0 | 4 | 0 | 0 | $0.208 | 157454 |
| real-skills/skills/xlsx/SKILL.md | shell | certified (8.2) | 4 | 2 | 0 | 0 | 2 | 0 | $0.3 | 581727 |
| real-skills/skills/xlsx/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (2.9) | 4 | 0 | 0 | 4 | 0 | 0 | $0.228 | 209766 |
| real-skills/skills/docx/SKILL.md | shell | certified (9.2) | 4 | 3 | 0 | 0 | 1 | 0 | $0.257 | 583559 |
| real-skills/skills/docx/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.7) | 4 | 0 | 0 | 4 | 0 | 0 | $0.182 | 121589 |
| benchmarks/spec-cases/order-in-budget/A/SKILL.md | shell | certified (13.2) | 4 | 4 | 0 | 0 | 0 | 0 | $0.094 | 210329 |
| benchmarks/spec-cases/publish-with-approval/A/SKILL.md | shell | certified (7.5) | 4 | 4 | 0 | 0 | 0 | 0 | $0.122 | 304949 |
| benchmarks/spec-cases/onboard-badge/A/SKILL.md | shell | certified (6.2) | 4 | 4 | 0 | 0 | 0 | 0 | $0.114 | 290417 |
| benchmarks/spec-cases/ledger-verify/A/SKILL.md | shell | certified (4.6) | 4 | 4 | 0 | 0 | 0 | 0 | $0.173 | 334143 |
| benchmarks/spec-cases/order-in-budget/B/SKILL.md | shell | refuted:GOAL_UNSAT (11.1) | 4 | 0 | 0 | 4 | 0 | 0 | $0.08 | 130090 |
| benchmarks/spec-cases/publish-with-approval/B/SKILL.md | shell | refuted:BLOCKED_GUARD (4.1) | 4 | 0 | 2 | 2 | 0 | 0 | $0.127 | 301949 |
| benchmarks/spec-cases/onboard-badge/B/SKILL.md | shell | refuted:GOAL_UNSAT (1.8) | 4 | 0 | 0 | 4 | 0 | 0 | $0.122 | 279752 |
| benchmarks/spec-cases/ledger-verify/B/SKILL.md | shell | refuted:MISSING_CAPABILITY (1.3) | 4 | 0 | 0 | 2 | 2 | 0 | $0.14 | 356128 |
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | shell | certified (11.1) | 4 | 4 | 0 | 0 | 0 | 0 | $0.258 | 523112 |
| real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (5.6) | 4 | 0 | 0 | 4 | 0 | 0 | $2.532 | 2474309 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | shell | certified (10.1) | 4 | 4 | 0 | 0 | 0 | 0 | $0.293 | 596804 |
| real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (3.1) | 2 | 0 | 1 | 1 | 0 | 0 | $0.64 | 1067664 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | shell | certified (20.2) | 4 | 3 | 1 | 0 | 0 | 0 | $0.307 | 599216 |
| real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (4.1) | 4 | 0 | 1 | 0 | 3 | 0 | $3.878 | 3641064 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | shell | certified (12.7) | 4 | 4 | 0 | 0 | 0 | 0 | $0.324 | 580349 |
| real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (5.6) | 4 | 0 | 1 | 1 | 2 | 0 | $3.313 | 3951603 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | shell | certified (12.5) | 4 | 4 | 0 | 0 | 0 | 0 | $0.463 | 890412 |
| real-skills-ext/obra__superpowers/writing-skills/SKILL.md | no-shell | refuted:MISSING_CAPABILITY (5.6) | 4 | 0 | 2 | 0 | 2 | 0 | $2.847 | 3149738 |
