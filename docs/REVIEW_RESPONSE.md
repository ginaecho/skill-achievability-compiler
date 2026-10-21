# Review response: what was built, measured and changed (2026-10-15)

The VerifyAgents reviews (meta-review; reviewers JaUr, ri6M, ijdA, km6X) left five points
open. This document is the index of what was done about each, with the numbers as measured.
The pre-registered plan, its addenda and the run directories are under
`runs/20261015_review_response/PLAN.md`. Nothing here is a resubmission.

Every number below comes from a run whose prompts and replies are on disk with sha256s. Where
a pre-registered criterion was not met, it says so.

## 1. Protocol rejections were reported as IMPOSSIBLE without a covering theorem

**Change.** The verdict now has two dimensions. Goal reachability is `ACHIEVABLE`,
`IMPOSSIBLE` or `UNKNOWN`; protocol typing is `WELL_TYPED`, `REJECTED` or `NOT_CHECKED`.
`NON_PROJECTABLE` and `NON_CONFORMANT` are protocol reasons and never produce `IMPOSSIBLE`.
Each verdict carries `coverage` (which formal result covers the goal verdict) and
`protocol_coverage`. Hosts (the Agent 365 gate, the Agent Framework middleware, the Scout and
Copilot adapters) allow a plan only when it is `admissible`: goal reachable and protocol not
rejected. The reviewer's two-branch scenario is a test
(`test_one_nonconformant_branch_does_not_refute_a_goal_another_branch_reaches`).

**Effect on the paper's corpus.** Two of the fifteen cases were relabelled after hand
checking: `deadlock_unobserved` and `nonconformant_handler` are goal-reachable with the
protocol rejected. Goal dimension: 6 refuted, 7 achievable, 2 planted residue cases; protocol
dimension: 11 correct, 0 false rejections, 0 missed, 4 not checked.

Details: `docs/VERDICT_COVERAGE.md`.

## 2. Compaction was never evaluated

**Experiment R** (`docs/COMPACTION_RELIABILITY.md`, `runs/20261015_reliability/`): 100 real
documents (set2: 70 SKILL.md, 30 agent.md, blind requirement labels verified by read-only
probes; 31 BLOCKED, 69 ACHIEVABLE), gpt-5.4 compaction, 5 samples per document, DeepSeek-V4-Pro
as a second family, a Claude judge for fidelity.

| measure | value | criterion |
|---|---|---|
| schema gate, valid first reply / after one retry | 0.678 / 0.924 | R1 >= 0.95: not met |
| all five samples agree / Fleiss' kappa | 0.39 / 0.26 | R2: not met |
| false refutations of ACHIEVABLE documents | 11/69 (15.9%) | R3 <= 10%: not met |
| decided accuracy, skillc vs direct LLM verdict | 0.682 vs 0.794 | R4 within 5 points: not met |
| recall of BLOCKED documents, skillc | 7/31 | |
| fidelity: no invented Tool / no invented ordering | 0.91 / 0.90 | R5 >= 0.85: met |
| fidelity: no omitted mandatory step / Goal names deliverable / bindings plausible | 0.63 / 0.73 / 0.68 | |
| second judge agreement / pooled kappa (18 items) | 0.81 / 0.47 | |

DeepSeek-V4-Pro produced valid Controlled English for 16 of 100 documents, so cross-model
agreement of packs could not be measured; the two direct-verdict arms agree at kappa 0.54.

## 3. No baseline

Same set, same documents (`docs/COMPACTION_RELIABILITY.md`):

| arm | decided accuracy | BLOCKED recall | false refutations |
|---|---|---|---|
| direct LLM verdict, gpt-5.4 | 0.794 | 29/31 | 18/69 |
| direct LLM verdict, DeepSeek-V4-Pro | 0.684 | 29/31 | 29/69 |
| planner only on the capability layer | 0.682 | 6/31 | 10/69 |
| tool lint (withdrawn or blocked tool) | 0.773 | 5/31 | 1/69 |
| skillc (full checker) | 0.682 | 7/31 | 11/69 |
| always ACHIEVABLE | 0.69 | 0 | 0 |

The protocol layer added nothing to verdict accuracy on this set (skillc and the planner
differ on 2 of 88 documents). The direct verdict is more accurate and catches far more blocked
documents, at a higher false-refutation rate and without a witness.

## 4. The 87x saving was a model stated as fact

**Experiment C** (`docs/TOKEN_ECONOMICS.md`, `runs/20261015_cost/`): 31 BLOCKED and 31
ACHIEVABLE documents of set2; an ungated gpt-5.4 agent in a bounded simulation (real model
calls, tool results simulated from the annotators' verified observations) against one
metered compaction.

| quantity | measured | the model predicted |
|---|---|---|
| ungated run on a BLOCKED document, median tokens | 9,486 | 217,044 |
| compaction, median tokens | 6,289 | 3,950 |
| leverage on BLOCKED documents | 1.58x [1.01, 2.11] | 51x for these documents; 87x in the paper |
| overhead on ACHIEVABLE documents | 0.36 of one run | 0.03 to 0.04 |
| ungated agent: honest stop / claimed completion on BLOCKED | 68% / 32% | |

The agent stopped or claimed success after about two turns, so the model's quadratic term
never grew. `docs/TOKEN_ECONOMICS.md` now leads with the measured section; the cost model
follows under "A model, not a measurement"; every modelled figure is labelled.

## 5. Host evidence rested on authored packs

**Experiment H** (`docs/HOSTS_E2E.md`, `runs/20261015_hosts/`), gpt-5.4 compaction from the
natural-language inputs.

- **Agent 365.** With the environment's state names in the manifest, 189 of 195 static checks
  agree with the authored expectations; with the names hidden, 0 of 195 (no verdicts: every
  pack is `unaligned`). New separation-of-duty checks: authored packs 2/2, compacted packs 0/12,
  because every compacted pack collapses approver and actor into one role.
- **Agent Framework (finance hosted agent).** First run: 6 of 9 false IMPOSSIBLE on correct
  configurations. After the fixes below and compaction against the effective runtime: 0 of 9,
  7 of 9 labels equal to the authored pack's. The email-deliverable variant is no longer
  refuted: all three samples drop the email step (criterion B4 half met). A second multi-role
  case (`hosted-agent-finance-group`) gives 0 false IMPOSSIBLE and 3 protocol rejections.
- **Scout.** 70 SKILL.md against `scout-desktop`: 67 valid, 48 ACHIEVABLE (25 with the protocol
  rejected), 19 IMPOSSIBLE, 0 UNKNOWN; fidelity on 20: no invented Tool 0.60, no invented
  ordering 0.70, two judges agreeing on 20 of 20 shared answers. No truth exists for this
  runtime.

## Fixes made from the measurements, and their blind validation

Reading the refuted packs gave eight compaction defect classes (D1 to D8 in the plan). Fixes:
branch assumptions (`assuming`) for environment-decided facts; a universal `reply` tool for
deliverables written in the answer; prompt rules on message effects, Goal contents and one
Role per named actor; two retries; a parser that merges repeated Tool clauses; hosted-agent
compaction against the effective runtime; and a deterministic requirement reader evaluated
against the manifest (`docs/REQUIREMENT_EVALUATION.md`).

Validation on **set3**, a fresh 100-document set drawn disjoint from sets 1 and 2 and
labelled blind by ten annotators against the manifest text (82 ACHIEVABLE, 18 BLOCKED;
judgement labels, weaker than set2's probe-verified ones):

| arm | decided accuracy | BLOCKED recall (pooled, 3 samples) | false refutations (pooled) |
|---|---|---|---|
| P2g (before) | 0.681 | 22/54 (0.41) | 50/246 (20%) |
| P2g+ (after) | 0.844 | 4/54 (0.07) | 2/246 (0.8%) |
| requirement reader alone | 0.830 | 8/18 (0.44) | 7/82 (8.5%) |
| P2g+ with the requirement reader | 0.806 | 0.44 | 23/246 (9.3%) |
| direct LLM verdict | 0.771 | 16/18 (0.89) | 20/82 (24%) |

| criterion | result |
|---|---|
| B1 false refutations at most half of before | met (50 to 2) |
| B2 recall within 5 points of before | not met (0.41 to 0.07) |
| B3 fidelity higher than before | not met (no invented Tool 0.90 to 0.60, the `reply` steps count as invented; no invented ordering 0.83 to 0.90; bindings plausible 0.57 to 0.87) |
| B4 finance agent | half met (0 false IMPOSSIBLE; email variant not refuted) |
| C1 union recall within 5 points of the direct verdict | not met (0.44 vs 0.89) |
| C2 union false refutations at most 10% | met (9.3%) |
| C3 reader has no false refutations | not met (7 reader bugs: optional or example mentions read as hard) |

The union of the requirement reader and P2g+ dominates the old method on both axes, so it is
the default LLM path (`skillc check --llm`): deterministic markdown front-end, then the
requirement reader against the manifest, then compaction and the checker. The direct LLM
verdict remains more sensitive and remains a reported baseline.

## Addendum: a decision model on the compaction layer (Decision-1)

`Microsoft-Decision-1` (Foundry deployment `Decision-1`) is a decision-scoring model, not a
generative one: it returns probabilities for typed questions and cannot write Controlled
English, so it cannot compact. Addendum D of the plan tests it on data already on disk as a
fidelity judge of the compaction packs (X1), as a direct verdict (X2) and as a hardness filter
on refutations (X3, exploratory). Two of ten checks met: accuracy within 5 points of the gpt-5.4
direct verdict on set2 (0.770 vs 0.794; not on set3, 0.680 vs 0.771), and the filter on P2g+'s
six refutations. As a judge it agrees with the Claude judge at 0.73 to 0.75 (kappa about 0.1)
and reverses the sign of the set3 F1 finding, so it is not an admissible second judge. Details
and tables: `docs/DECISION_MODEL.md`, run `runs/20261015_decision1/`.

## What is still open

- Recall. The deterministic pipeline refutes safely but misses most blocked documents; the
  model does not write `needs` for a refused host, a missing GPU or an absent account, and the
  requirement reader only catches what a command, import, credential variable or tool
  reference makes explicit.
- The requirement reader reads optional, alternative and example mentions as hard in 7 of 82
  cases; fixing that needs a fourth blind set to measure.
- The universal `reply` tool lowers fidelity as judged: packs gain reply steps the document
  never asks for. The rubric needs a rule for deliverables written in the answer, or the
  prompt needs to confine `via reply` to a stated deliverable.
- Multi-actor documents compact into one role unless the prompt is told the roles.
- Environment contracts need the environment's state vocabulary; without it the checker gives
  no verdict.
- The vendored copies of skillc under `examples/hosted-agent-finance*/src/` are behind the
  package.
- Every held-out set used today is now consumed; any further change needs a new set.
