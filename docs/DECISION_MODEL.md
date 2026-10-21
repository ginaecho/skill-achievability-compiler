# Decision-1 on the compaction layer (PLAN.md Addendum D)

Run directory: `runs/20261015_decision1/` (prompts, outputs, `frozen.json`, `metrics.json`,
`filter_units.json`, `run.log`). Script: `scripts/decision1.py` (`judge`, `verdict`,
`filter`, `score`). Client: `skillc.frontend.providers.decision()`, tested in
`tests/test_decision_provider.py`. Pre-registration: `runs/20261015_review_response/PLAN.md`,
Addendum D (its sha256 is in `frozen.json` and `metrics.json`).

## What the model is

`Microsoft-Decision-1`, deployed as `Decision-1` on `foundary-tzuc06`, is not a chat model.
A request carries a `state` (text or JSON) and typed questions: `noul` (a yes/no
probability), `choice` (one option, with a probability per option) and `score` (an ordered
scale). The reply is numbers only, at `<resource>/providers/microsoft/v1/systemone`. It
cannot write text, so it cannot write Controlled English and cannot replace the compactor.
It can judge a compaction output, give a direct verdict, or say whether a requirement is
hard.

Every request went out once, at most 40 requests per minute: 489 calls, 1,770,141 input
tokens, 1,361 output tokens. No request failed and no document was truncated (the
service limit for the state plus the questions is 64,000 tokens; no item came near it).
No item was excluded.

## X1: Decision-1 as fidelity judge

State = {source document, runtime, Controlled English pack}; five `noul` questions F1..F5.
Each `instructions` is the item's rubric text. Each `criteria` pair is a yes/no condition
derived from the rubric and the judge README notes (constants `JUDGE_CRITERIA` in the
script). No Claude score is in any request. A probability >= 0.5 counts as yes. Claude
`unclear` answers are dropped from the pairwise agreement.

Pooled over F1..F5:

| Set | Items | Agreement with judge 1 | Kappa | AUROC vs judge 1 | Agreement with judge 2 | Judge 2 vs judge 1 (unclear kept / dropped) |
|---|---|---|---|---|---|---|
| set2 | 88 | 0.730 (302/414) | 0.11 | 0.56 | 0.759 (n 87) | 0.811 / 0.880 (18 items) |
| set3 | 60 | 0.752 (206/274) | 0.10 | 0.60 | 0.767 (n 60) | 0.850 / 0.895 (12 items) |
| Scout | 20 | 0.723 (68/94) | 0.29 | 0.68 | 0.550 (n 20) | 1.000 / 1.000 (4 items) |

Yes-rates (Decision-1 / Claude judge 1, Claude rate with `unclear` in the denominator):

| Set | F1 | F2 | F3 | F4 | F5 |
|---|---|---|---|---|---|
| set2 | 0.63 / 0.91 | 0.92 / 0.63 | 0.56 / 0.73 | 0.97 / 0.90 | 0.98 / 0.68 |
| set3 | 0.48 / 0.75 | 0.95 / 0.65 | 0.75 / 0.83 | 0.97 / 0.87 | 1.00 / 0.72 |
| Scout | 0.40 / 0.60 | 0.85 / 0.60 | 0.65 / 0.75 | 0.95 / 0.70 | 0.95 / 0.70 |

Per-criterion kappas with judge 1 are between -0.05 and 0.32 on set2 and set3. Decision-1
says yes to F2, F4 and F5 almost every time. Its probability ranks F3 best (AUROC 0.83 on
set2, 0.74 on set3).

Set3, P2g -> P2g+ (30 documents each):

| Criterion | Decision-1 | Claude judge 1 | Same sign |
|---|---|---|---|
| F1 | 0.433 -> 0.533 (+0.10) | 0.90 -> 0.60 (-0.30) | no |
| F4 | 0.967 -> 0.967 (0.00) | 0.833 -> 0.90 (+0.07) | no |

- **X1a (not met on either set).** Decision-1's agreement with judge 1 is 0.730 on set2
  (reference 0.811) and 0.752 on set3 (reference 0.850). It also stays below the stricter
  reference that drops `unclear` (0.880, 0.895).
- **X1b (not met).** The F1 change has the opposite sign, and Decision-1 shows no F4 change.

Decision-1 is not an admissible second judge, so the B3 finding still rests on the Claude
judges.

## X2: Decision-1 as direct verdict (arm D-dec)

State = {"instructions": D system prompt, "input": D user text}: the same words that
gpt-5.4 D read. The questions are a `blocked` `noul` and a `verdict` `choice`
(ACHIEVABLE / IMPOSSIBLE / UNKNOWN), each with the D prompt's definitions. The verdict is
the `choice`.

| Set | Arm | Decided acc. (95% CI) | UNKNOWN | BLOCKED recall (95% CI) | False refutations (95% CI) |
|---|---|---|---|---|---|
| set2 | D-dec | 0.770 [0.68, 0.84] (77/100) | 0 | 0.871 (27/31) [0.71, 0.95] | 19/69 [0.18, 0.39] |
| set2 | D gpt-5.4 | 0.794 [0.70, 0.86] (77/97) | 3 | 0.935 (29/31) [0.79, 0.98] | 18/69 [0.17, 0.38] |
| set3 | D-dec | 0.680 [0.58, 0.76] (68/100) | 0 | 0.833 (15/18) [0.61, 0.94] | 29/82 [0.26, 0.46] |
| set3 | D gpt-5.4 | 0.771 [0.68, 0.84] (74/96) | 4 | 0.889 (16/18) [0.67, 0.97] | 20/82 [0.16, 0.35] |

| Set | McNemar vs D gpt-5.4 | AUROC of P(blocked) | Threshold matching D recall | False refutations there | D gpt-5.4 |
|---|---|---|---|---|---|
| set2 | 8 vs 9 discordant, p = 1.0 | 0.890 | 0.35 (recall 0.935) | 23/69 | 18/69 |
| set3 | 4 vs 12 discordant, p = 0.077 | 0.850 | 0.30 (recall 0.889) | 33/82 | 20/82 |

"Threshold matching D recall" is the highest threshold on the 0.05 grid whose recall is at
least gpt-5.4 D's recall. The full operating curves (0.05..0.95) are in `metrics.json`
(`X2_verdict.<set>.operating_curve`).

- **X2a.** Met on set2 (-2.4 points). Not met on set3 (-9.1 points).
- **X2b.** Not met on either set. At gpt-5.4 D's recall, Decision-1 makes 5 (set2) and 13
  (set3) more false refutations.

Cost: 100 calls per set, 347,662 (set2) and 383,091 (set3) input tokens, 2 output tokens
per call.

## X3: hardness filter on set3 refutations (exploratory)

For each refutation there is one request per refuting requirement. For Rdet, that is each
witness requirement with its evidence lines. For P2g+ and P2g, it depends on the refutation:
- a refutation with a blocked `needs`: the resource, with the Tool lines that carry it;
- a guard that cannot be satisfied: the step, with its Tool line and the guard text;
- GOAL_UNSAT: the goal facts that no Tool establishes, with the Goal line.

A refutation is kept when any of its requirements is kept. Default rule: `choice == hard`.
Second rule: P(hard) >= 0.7. Units: Rdet 22, P2g+ 6, P2g 93 (`filter_units.json`).

| Arm | Rule | True refutations kept | False refutations removed | X3 |
|---|---|---|---|---|
| Rdet | default | 5/8 (0.63) | 6/7 (0.86) | not met |
| Rdet | P(hard) >= 0.7 | 4/8 (0.50) | 6/7 (0.86) | not met |
| P2g+ | default | 4/4 (1.00) | 1/2 (0.50) | met |
| P2g+ | P(hard) >= 0.7 | 4/4 (1.00) | 2/2 (1.00) | met |
| P2g | default | 17/22 (0.77) | 6/50 (0.12) | not met |
| P2g | P(hard) >= 0.7 | 12/22 (0.55) | 10/50 (0.20) | not met |

The reader's (Rdet) seven false refutations on set3:

| Case | Requirement: choice, P(hard) | Kept (default / 0.7) |
|---|---|---|
| c001 | account:render_account: hard, 0.71 | yes / yes |
| c005 | account:hcp_account: example_or_mention_only, 0.26; account:aws_account: example_or_mention_only, 0.26 | no / no |
| c006 | account:aws_account: example_or_mention_only, 0.02 | no / no |
| c027 | daemon:docker: optional_or_alternative, 0.07; program:docker: optional_or_alternative, 0.13 | no / no |
| c032 | credential:FOUNDRY_API_KEY, account:llm_api_key, account:azure_account: all optional_or_alternative, <= 0.03 | no / no |
| c047 | platform:windows: example_or_mention_only, 0.01 | no / no |
| c081 | account:aws_account: example_or_mention_only, 0.02 | no / no |

The filter also removes 3 of Rdet's 8 true refutations: c031 (platform:macos), c034
(account:llm_api_key) and c040 (account:aws_account, `cannot_tell`). At 0.7 it also removes
c061 (mcp:atlassian, P(hard) 0.37). On P2g, most false refutations are GOAL_UNSAT
compaction defects (38 of 50). The filter keeps nearly all of them, because the goal facts
are part of the task.

Caveat, verbatim from the plan: "The reader's seven false refutations on set3 were found by
reading set3, so a filter that addresses them is tested on the set that produced them: X3
is optimistic by construction and is reported as exploratory; a confirmatory number needs
set4. X1 and X2 are not optimistic in this sense (Decision-1 has not seen any of the
documents and nothing is tuned on them)."

## Criteria summary

| Criterion | Result |
|---|---|
| X1a set2 | not met (0.730 < 0.811) |
| X1a set3 | not met (0.752 < 0.850) |
| X1b | not met (F1 +0.10 vs -0.30; F4 0.00 vs +0.07) |
| X2a set2 | met (0.770 vs 0.794) |
| X2a set3 | not met (0.680 vs 0.771) |
| X2b set2 | not met (23 vs 18 false refutations at recall 0.935) |
| X2b set3 | not met (33 vs 20 false refutations at recall 0.889) |
| X3 Rdet | not met (default: 5/8 kept, 6/7 removed) |
| X3 P2g+ | met under both rules (n = 6) |
| X3 P2g | not met (default: 17/22 kept, 6/50 removed) |
