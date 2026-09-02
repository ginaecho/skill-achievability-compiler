# Baseline: why not just ask a language model?

**Status: not run.** Both judge rows below are `scored: 0` -- the model calls
failed with authentication errors and were never retried, so this baseline
produced no data and the paper does not cite it. The artifact is kept because
the harness and the ground-truth table are real and re-runnable
(`python3 scripts/llm_judge_baseline.py`); the comparison the file was built
for is future work, and the paper's only baseline is the token-free one in
`scripts/grep_baseline.py`.

24 configurations whose answer is known independently of the checker: 8 by construction (the authored specification pairs) and 16 by observation (settled by verified agent runs at realistic input size).

| decider | scored | correct | accuracy | says achievable, is not | says impossible, is not | tokens | cost |
|---|---|---|---|---|---|---|---|
| **checker** | 24 | 24 | 1.0 | 0 | 0 | **0** | **$0** (131.9 ms) |
| LLM judge (haiku), majority of 3 | 0 | 0 | None | 0 | 0 | 0 | $0.0 |
| LLM judge (sonnet), majority of 3 | 0 | 0 | None | 0 | 0 | 0 | $0.0 |

## Per configuration

| skill | runtime | truth | source | checker | judge haiku | judge sonnet |
|---|---|---|---|---|---|---|
| `benchmarks/spec-cases/order-in-budget/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | None ✗ | None ✗ |
| `benchmarks/spec-cases/order-in-budget/B/SKILL.md` | shell | not | constructed | refuted ✓ | None ✗ | None ✗ |
| `benchmarks/spec-cases/publish-with-approval/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | None ✗ | None ✗ |
| `benchmarks/spec-cases/publish-with-approval/B/SKILL.md` | shell | not | constructed | refuted ✓ | None ✗ | None ✗ |
| `benchmarks/spec-cases/onboard-badge/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | None ✗ | None ✗ |
| `benchmarks/spec-cases/onboard-badge/B/SKILL.md` | shell | not | constructed | refuted ✓ | None ✗ | None ✗ |
| `benchmarks/spec-cases/ledger-verify/A/SKILL.md` | shell | achievable | constructed | achievable ✓ | None ✗ | None ✗ |
| `benchmarks/spec-cases/ledger-verify/B/SKILL.md` | shell | not | constructed | refuted ✓ | None ✗ | None ✗ |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md` | no-shell | not | observed | refuted ✓ | None ✗ | None ✗ |
| `real-skills-ext/K-Dense-AI__claude-scientific-skills/bulk-rnaseq/SKILL.md` | shell | achievable | observed | achievable ✓ | None ✗ | None ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md` | no-shell | not | observed | refuted ✓ | None ✗ | None ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/data-quality-auditor/SKILL.md` | shell | achievable | observed | achievable ✓ | None ✗ | None ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md` | no-shell | not | observed | refuted ✓ | None ✗ | None ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/google-workspace-cli/SKILL.md` | shell | achievable | observed | achievable ✓ | None ✗ | None ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md` | no-shell | not | observed | refuted ✓ | None ✗ | None ✗ |
| `real-skills-ext/alirezarezvani__claude-skills/kubernetes-operator/SKILL.md` | shell | achievable | observed | achievable ✓ | None ✗ | None ✗ |
| `real-skills-ext/obra__superpowers/writing-skills/SKILL.md` | no-shell | not | observed | refuted ✓ | None ✗ | None ✗ |
| `real-skills-ext/obra__superpowers/writing-skills/SKILL.md` | shell | achievable | observed | achievable ✓ | None ✗ | None ✗ |
| `real-skills/skills/docx/SKILL.md` | no-shell | not | observed | refuted ✓ | None ✗ | None ✗ |
| `real-skills/skills/docx/SKILL.md` | shell | achievable | observed | achievable ✓ | None ✗ | None ✗ |
| `real-skills/skills/pdf/SKILL.md` | no-shell | not | observed | refuted ✓ | None ✗ | None ✗ |
| `real-skills/skills/pdf/SKILL.md` | shell | achievable | observed | achievable ✓ | None ✗ | None ✗ |
| `real-skills/skills/xlsx/SKILL.md` | no-shell | not | observed | refuted ✓ | None ✗ | None ✗ |
| `real-skills/skills/xlsx/SKILL.md` | shell | achievable | observed | achievable ✓ | None ✗ | None ✗ |
