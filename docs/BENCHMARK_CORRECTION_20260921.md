# Corrected SkillC benchmark and refutation accuracy

Date: 2026-09-21. This report separates compiler correctness, simulated
runtime costs, and the question "does an IMPOSSIBLE verdict mean the goal
really cannot be achieved?"

## Confirmed defects and repairs

Five minimal regressions failed before repair:

| Defect | Observable failure | Repair |
|---|---|---|
| Separate goal/conformance queries | The goal can require initial `x = 0` while conformance requires `x = 1`, yet the checker accepts | Include the goal and world-sensitive conformance condition in the same satisfiability query |
| First-witness selection | The first branch's witness is incompatible with conformance, although another branch works | Search again with the joint condition at every goal, rather than checking only the first candidate |
| Ignored action guards | The simulator reports success for `publish` without its required `approved` predicate | Reject the transition and preserve the world when its precondition is false |
| Missing numeric semantics | Numeric assignments are ignored and numeric goals silently evaluate false | Interpret integer expressions, initial constraints, simultaneous assignments, constrained nondeterminism, and numeric goals |
| Reversed overlapping effects | A predicate in both add/delete remains true in the simulator | Apply add then delete, matching the declared world semantics |

The first two are implementation errors relative to the checker's intended
joint conformance/reachability condition. They do not establish a flaw in the
Coq theorem. The simulator errors are confirmed at the actual runtime-trial
entry point, using deterministic model-response fixtures.

The repaired interpreter is in
[`scripts/benchmark_semantics.py`](../scripts/benchmark_semantics.py). It does
not call `skillc.checker` to decide whether a simulated action succeeds.
Unsupported expressions and unbound numeric values raise errors rather than
silently becoming failed goals. An unsatisfiable effect rejects an action.
Solver `UNKNOWN` is an explicit benchmark error, not proof of impossibility.

Original regression command:

```powershell
python -m pytest -q tests\test_checker.py tests\test_real_rejection_benchmark.py -k "terminal_goal_and_conformance or joint_typing_search or runtime_rejects_action or runtime_applies_numeric or runtime_delete_wins"
```

Before repair: **5 failed**. After repair, the full suite reports
**329 passed, 11 skipped**. The skipped checks include Coq compilation
(`coqc` is unavailable), opt-in live compaction tests, and absent external
skill-corpus checks. The separate live benchmark is described below.

## Ground truth: failure is not impossibility

Two distinct questions must not be combined into one accuracy number:

1. **Declared-contract admissibility:** does the specific pack meet the
   capability, protocol, conformance, and reachability requirements?
2. **Any-plan goal reachability:** can some sequence of the available
   capabilities achieve the stated goal, even if the declared protocol is
   malformed or mentions an unnecessary unavailable action?

A compiler can reject the first while the answer to the second is yes.
Therefore a protocol rejection alone is not evidence that no alternative
workflow could achieve the business goal.

This evaluation uses two independently identified sources of labels:

- The repository's existing curated reference-corpus labels, including two
  intentionally spurious intent/payload cases. These are not a fresh
  real-world ground-truth audit.
- A separate action-level oracle for the saved real-skill packs. It can
  prove impossibility from missing goal establishers or exhaustive Boolean
  state exploration, or prove possibility by recording a concrete
  goal-reaching sequence of legal transitions. Numeric or bounded searches
  without a witness abstain. They do not label a task impossible simply
  because search or an agent failed.

The action-level oracle deliberately ignores protocol/session admissibility.
It judges the broader goal question. Its proofs and witnesses are relative
to the declared capability effects, not independently tested live tools.
The checker and oracle share Z3 as a solver, but not transition or
reachability implementation.

## Precision, recall, and false positives

**Positive means `IMPOSSIBLE`.** This reverses the legacy `skillc eval`
matrix, where positive means `ACHIEVABLE`.

```text
TP: truly impossible, rejected
FP: achievable, rejected
FN: impossible, admitted
TN: achievable, admitted

Precision = TP / (TP + FP)
Recall    = TP / (TP + FN)
FPR       = FP / (FP + TN)
```

An unknown prediction or unknown reference label is excluded from the
decided matrix and reported separately. Undefined ratios remain null,
not zero. `refutation_metrics()` also reports recall across all labelled
impossible cases, including those for which the checker abstains.

| Evaluation scope | Scored cases | TP | FP | FN | TN | Precision | Recall | FPR |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Curated reference corpus | 15 | 7 | 0 | 2 | 6 | 100% | 77.78% | 0% |
| Extended reference corpus | 5 | 3 | 0 | 0 | 2 | 100% | 100% | 0% |
| Five real-skill packs, complete and restricted profiles, against any-plan goal reachability | 10 | 4 | 5 | 0 | 1 | 44.44% | 100% | 83.33% |
| Restricted profiles only, against any-plan goal reachability | 5 | 4 | 1 | 0 | 0 | 80% | 100% | 100% |

The extended corpus has six cases in total: one `UNKNOWN` reference and
prediction is excluded. Its decision coverage over all six is 83.33%;
coverage of its five labelled cases is 100%. All other rows have full
labelled coverage.

The curated corpus's two misses are `spurious_payload` and
`spurious_intent`. Its zero false positives is a result on this small,
curated set, not proof of 100% precision on arbitrary skills.

### Why the real-pack goal-level precision is lower

All five complete-profile goals have constructive action-level witnesses.
The checker admits algorithmic-art but rejects the other four complete
packs as `NON_CONFORMANT`. These are four false rejections if its verdict
is interpreted as *any-plan goal impossibility*, not necessarily four
errors in checking the narrower declared contract.

For restricted profiles, four goals have missing-establisher proofs.
The restricted web-app-testing goal is different: it is a disjunction
that can be satisfied without the missing cleanup capability. The
checker rejects the declared protocol as `MISSING_CAPABILITY`, while an
alternative allowed sequence satisfies the goal. This is the fifth
goal-level false rejection across the ten profiles.

The correct claim is therefore not "every rejection proves the business
goal impossible." Some rejections say "this declared protocol is not
admissible." The metrics above expose that distinction rather than
silently changing the labels or weakening the goals to improve scores.

## Corrected with/without comparison

Run:
[`runs/20260921_110234Z_real_rejection_benchmark`](../runs/20260921_110234Z_real_rejection_benchmark/).
These are local benchmark artifacts; links require the run directory.

The runtime comparison uses five restricted skill profiles, five trials
per profile, and at most eight model turns per trial. GPT-5.4 chooses
actions through real Azure OpenAI calls; the backend actions are
**simulated**, not actual browser/build/GIF operations.

The six historical compaction calls are reused after checking the source
and license hashes and matching each saved pack to its recorded model
output. Their measured costs are attributed once per skill, not charged
again as new API calls. New runtime costs come from the fresh provider
usage records. The trusted static checker consumes zero model tokens,
but its CPU latency is measured.

The simulator chooses one satisfying numeric outcome with a fixed solver
seed. It does not sample a real backend's outcome distribution. Its
eight-turn limit measures bounded attempts, not an impossibility proof.
The ungated agent can choose alternative plans; it is not restricted to
replaying the original protocol. This is why protocol rejection and
goal-level ground truth are reported separately.

The run completed with **92 fresh model calls**, all HTTP 200 with finish
reason `stop`, using resolved model **`gpt-5.4-2026-03-05`**. The provider
ledger reconciles to **260,242 runtime tokens**. All 69 recorded attempted
transitions were checked against preconditions, simultaneous numeric
effects, predicate framing, and final-state goal satisfaction.

| Restricted skill | Independent goal label | With SkillC: historical compaction once | Without SkillC: fresh tokens over five trials | Verified runtime successes |
|---|---|---:|---:|---:|
| Web-app testing | ACHIEVABLE | 3,787 | 20,073 | 2/5 |
| MCP builder | IMPOSSIBLE | 4,338 | 94,542 | 0/5 |
| Frontend design | IMPOSSIBLE | 4,039 | 59,791 | 0/5 |
| Slack GIF creator | IMPOSSIBLE | 8,737 | 12,182 | 0/5 |
| Algorithmic art | IMPOSSIBLE | 5,778 | 73,654 | 0/5 |
| All five | Mixed | 26,679 | 260,242 | 2/25 |
| Four independently impossible cases only | IMPOSSIBLE | 22,892 | 240,169 | 0/20 |

SkillC rejects all five restricted protocols, so gated runtime execution
uses zero additional model tokens. That also prevents both successful
web-testing attempts. Do not count preventing those successes as a
benefit.

### Cost comparison on independently impossible cases

The four-case subset is selected by the independent impossibility proofs,
**not** by observing which runtime attempts failed.

| Accounting basis | With SkillC | Without SkillC | Reduction |
|---|---:|---:|---:|
| Cold first use: one invocation of each of four skills | 22,892 historical measured compaction tokens | 48,033.8 mean fresh runtime tokens | 52.34% |
| Five invocations per skill: compaction reused across 20 attempts | 22,892 historical measured compaction tokens | 240,169 fresh runtime tokens | 90.47% |
| Cached pack: marginal runtime model tokens after static rejection | 0 | Same measured ungated execution costs | 100% of runtime model tokens only |

The repeated-use difference is **217,277 tokens**. The first-use baseline
is the sum of per-skill means, not the full repeated-run token total.
The cached row excludes the already-paid compaction cost and does not
imply zero CPU cost.

Across all five cases, the raw token reduction would be 89.75% over five
repetitions, or 48.74% for one expected invocation per case. Those are
cost-only figures with a false-rejection tradeoff, not justified savings
from blocking impossible work.

Five restricted-pack static checks took a combined **2.83 ms** in this
measurement. The 92 fresh API calls account for **147.04 seconds** of
summed request latency. These are not comparable end-to-end latency
measurements: the checker time excludes historical compaction, and
summed API latency excludes some harness/setup overhead.

### Observed outcomes and limitations

All 20 attempts on the four impossible cases terminated `blocked`.
Web-app testing produced two verified simulated successes, two `blocked`
outcomes, and one model claim of success rejected as `false_success`.
This is direct evidence that protocol-level rejection can suppress a
goal-reaching alternative in this benchmark.

These are five skills and five trials per restricted profile, not a
representative population sample. The ten-profile accuracy table includes
offline complete-profile checks; complete profiles were **not** given
additional live runtime trials. The tests validate the interpreter's
declared semantics, not the real effects of external tools.

## Effect on previous results

Replaying the old recorded Boolean action sequences identifies nine of
25 trials that accepted a false precondition: four web-app-testing
trials, one MCP-builder trial, and four GIF-creator trials.
MCP-builder and GIF-creator also used numeric goals/effects that the old
simulator did not evaluate faithfully.

The old API usage records remain historical measurements. They cannot
be relabelled into corrected runtime costs: changed feedback can change
subsequent agent decisions. The September simulator's old success/failure
and savings figures are superseded for this purpose.

The separate 134-run experiment and its selected 46-run failure subset
were not rerun or regraded here. This report neither invalidates nor
recertifies those results.

## Reproduce

```powershell
python -m pytest -q
python scripts\benchmark_real_rejections.py --reuse-compactions runs\20260916_132708Z_real_rejection_benchmark --repetitions 5 --max-turns 8 --model gpt-5.4
```

Configure an Azure OpenAI endpoint/deployment and either
`AZURE_OPENAI_API_KEY` or the existing Azure CLI identity as required by
the harness. Do not put credentials in artifacts or command history.
The reuse command requires the local historical run; omitting
`--reuse-compactions` makes new compaction calls and can produce different
packs and costs.

Evidence files include `manifest.json` (revision, dirty state, source
hashes, and model configuration), `calls.jsonl` (provider usage),
`runtime_trials.jsonl` (durable completed trials), `accuracy.json`
(oracle witnesses/proofs and checker verdicts), `reference_metrics.json`,
`prior_run_audit.json`, and `verification.json` (reconciled totals and
transition checks). `source_snapshot/` preserves all 13 implementation
files hashed in the manifest, so later source edits cannot silently
change the implementation attributed to this run. Original historical
artifacts are preserved.
