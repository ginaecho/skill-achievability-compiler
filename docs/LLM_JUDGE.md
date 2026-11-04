# Baseline: why not just ask a language model?

34 configurations whose answer is known independently of the checker: 18 by construction (the authored specification pairs) and 16 by observation (settled by verified agent runs at realistic input size).

| decider | scored | correct | accuracy | says achievable, is not | says impossible, is not | tokens | cost |
|---|---|---|---|---|---|---|---|
| **checker** | 34 | 32 | 0.941 | 0 | 2 | **0** | **$0** (720.4 ms) |
| LLM judge (haiku), majority of 3 | 34 | 26 | 0.765 | 1 | 7 | 330723 | $0.055 |
| LLM judge (sonnet), majority of 3 | 34 | 29 | 0.853 | 0 | 5 | 329853 | $1.177 |

## Per configuration

| skill | runtime | truth | source | checker | judge haiku | judge sonnet |
|---|---|---|---|---|---|---|
| `benchmarks/spec-cases/index-then-search/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | True ✓ | True ✓ |
| `benchmarks/spec-cases/index-then-search/B/SKILL.md` | shell | not | constructed | refuted ✓ | True ✗ | False ✓ |
| `benchmarks/spec-cases/ledger-verify/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | True ✓ | True ✓ |
| `benchmarks/spec-cases/ledger-verify/B/SKILL.md` | shell | not | constructed | refuted ✓ | False ✓ | False ✓ |
| `benchmarks/spec-cases/migrate-with-quota/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | False ✗ | True ✓ |
| `benchmarks/spec-cases/migrate-with-quota/B/SKILL.md` | shell | not | constructed | refuted ✓ | False ✓ | False ✓ |
| `benchmarks/spec-cases/onboard-badge/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | True ✓ | True ✓ |
| `benchmarks/spec-cases/onboard-badge/B/SKILL.md` | shell | not | constructed | refuted ✓ | False ✓ | False ✓ |
| `benchmarks/spec-cases/order-in-budget/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | False ✗ | True ✓ |
| `benchmarks/spec-cases/order-in-budget/B/SKILL.md` | shell | not | constructed | refuted ✓ | False ✓ | False ✓ |
| `benchmarks/spec-cases/publish-with-approval/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | True ✓ | True ✓ |
| `benchmarks/spec-cases/publish-with-approval/B/SKILL.md` | shell | not | constructed | refuted ✓ | False ✓ | False ✓ |
| `benchmarks/spec-cases/quota-send/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | False ✗ | True ✓ |
| `benchmarks/spec-cases/quota-send/B/SKILL.md` | shell | not | constructed | refuted ✓ | False ✓ | False ✓ |
| `benchmarks/spec-cases/sign-then-ship/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | True ✓ | True ✓ |
| `benchmarks/spec-cases/sign-then-ship/B/SKILL.md` | shell | not | constructed | refuted ✓ | False ✓ | False ✓ |
| `benchmarks/spec-cases/two-person-release/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | True ✓ | True ✓ |
| `benchmarks/spec-cases/two-person-release/B/SKILL.md` | shell | not | constructed | refuted ✓ | False ✓ | False ✓ |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md` | no-shell | not | observed | refuted ✓ | False ✓ | False ✓ |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md` | shell | achievable | observed | achievable ✓ | True ✓ | True ✓ |
| `real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md` | no-shell | not | observed | refuted ✓ | False ✓ | False ✓ |
| `real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md` | shell | achievable | observed | achievable ✓ | True ✓ | True ✓ |
| `real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md` | no-shell | achievable | observed | refuted ✗ | False ✗ | False ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md` | shell | achievable | observed | achievable ✓ | True ✓ | False ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md` | no-shell | achievable | observed | refuted ✗ | False ✗ | False ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md` | shell | achievable | observed | achievable ✓ | True ✓ | True ✓ |
| `real-skills-ext/obra__superpowers/writing-skills/SKILL.md` | no-shell | achievable | observed | achievable ✓ | False ✗ | False ✗ |
| `real-skills-ext/obra__superpowers/writing-skills/SKILL.md` | shell | achievable | observed | achievable ✓ | False ✗ | False ✗ |
| `real-skills/skills/docx/SKILL.md` | no-shell | not | observed | refuted ✓ | False ✓ | False ✓ |
| `real-skills/skills/docx/SKILL.md` | shell | achievable | observed | achievable ✓ | True ✓ | True ✓ |
| `real-skills/skills/pdf/SKILL.md` | no-shell | not | observed | refuted ✓ | False ✓ | False ✓ |
| `real-skills/skills/pdf/SKILL.md` | shell | achievable | observed | achievable ✓ | True ✓ | True ✓ |
| `real-skills/skills/xlsx/SKILL.md` | no-shell | not | observed | refuted ✓ | False ✓ | False ✓ |
| `real-skills/skills/xlsx/SKILL.md` | shell | achievable | observed | achievable ✓ | True ✓ | True ✓ |
