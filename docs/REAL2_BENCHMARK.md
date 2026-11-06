# Real-use round 2: 300 new skills, blind execution, three repeats

Completed 2026-11-06 on `gc/paper-revision`.

**Result:** skillc catches more blocked skills than a direct model verdict, but
wrongly refutes more working skills and agrees less across repeats. C1 and C4
pass; C2 and C3 fail. The final 27 repeat-3 repairs use a user-approved successor
model and a different harness. These are mixed-model results, not a clean
single-model replication.

## Evidence and reproduction

- [Pre-registered plan and amendments 1-10](../runs/20261031_real2/PLAN.md).
- [Primary metrics](../runs/20261031_real2/metrics.json), including Wilson intervals,
  per-repeat runtime slices and sensitivities.
- [All 300 case outcomes](../runs/20261031_real2/case_outcomes.json): every label,
  inconclusive reason, arm, repeat and successor-repair case.
- [Supplementary analysis](../runs/20261031_real2/analysis.json): repository slices,
  pooled sensitivities, per-repeat costs and provenance-separated token totals.
- [Isolation audit](../runs/20261031_real2/isolation_audit.json),
  [call ledger](../runs/20261031_real2/calls.jsonl) and
  [checker timings](../runs/20261031_real2/checker_times.json).

On the completed branch, scoring makes no model calls:

```powershell
python scripts\real2.py score --model opus
```

`--model opus` selects the directory label, not a model alias for an inference
request. Amendment 4 selected one model; the unused frozen prompts for the other
three options are not failed runs. All 2,301 selected S/D jobs have output files:
1,401 S jobs and 900 D jobs. No missing-reply placeholder was needed.

## Method and continuation

The test set contains 300 previously unused skill-runtime pairs from 19 pinned
repositories, selected before the run. Each skill includes its bundled and
referenced support files. Runtime assignment is independent of skillc: developer
sandbox 110, offline workstation 76, office assistant 114.

S uses runtime-bound Controlled English compaction, static validation, one
located-error retry and one guarded counterexample-guided repair, without
pruning. D asks for a verdict directly against the same runtime. Three repeats
use independent contexts. Executors and adjudicators are blind to S/D verdicts.
The model identities are named in the paper; the ledger uses short hashes:

| Reported identity | Hash | Scope |
|---|---|---|
| Original model | `47a46a22` | Execution, adjudication, all D, all earlier S |
| Successor authorized by the user | `795584cf` | Only the final 27 S repeat-3 repair jobs |
| Synthetic error-message sentinel, not a serving model | `60d56aba` | Failed or interrupted original attempts |

The handoff estimated 67 remaining jobs; inspection found exactly 27 missing
frozen repair replies. Earlier replies were not rerun or changed. The original
3,139 ledger records were preserved and 28 new session records appended, including
one failed pilot, for **3,167 agent-attempt records**. A record is one agent
session, not necessarily one provider turn; usage is summed over its turns.

Every accepted continuation job had its own working directory, configuration
home and session ID. Memory was verified off using the installed CLI before
launch; history sync, custom instructions and automatic model fallback were
disabled. Only `view` and `create` were exposed, with file access restricted to
that job directory and no temporary-directory exception. The audit verified that
the tools read only that job's frozen prompt and created only its reply. No
agent context or memory was reused between jobs or retries.
The frozen repair prompt still contains its pre-registered within-case pack and
counterexample; outputs from other repeats are not supplied. Provider prompt
caching is distinct from loading another session's conversation.

The first pilot exposed installed-CLI compatibility issues: the settings file
is `settings.json`, and the writer is `create`, not `apply_patch`. It produced no
accepted reply and is retained as a failed cost record. Amendment 9 was committed
before its one permitted fresh-session retry. All subsequent jobs succeeded.
Native usage supplies the reported `model`; there is no separate backend-response
identity field in these transcripts.

All prompts and wrappers passed the URL guard. The ten URL-guard tests and seven
continuation tests passed; the changed Python files passed Ruff. Benchmark
documents were treated as data, not executed by the continuation agents.

### Truth isolation

Commit `ea8c907e` froze the completed replies and isolation audit before the truth
was opened. Only then was a detached worktree created at truth commit `e20f319d`
on the separate `gc/real2-truth` branch. Its 300 execution reports and 140
adjudications were collected through `collect-exec`; its 140 held-out adjudication
prompts and three batches were restored. The replaced pilot batch was backed up
outside the clone. The checksum-verified download remains unopened outside the
repository as a personal backup and is not committed.

## Ground truth: every case retained

| Label rule | Achieved | Blocked | Inconclusive | Decided |
|---|---:|---:|---:|---:|
| Main L2 | 140 | 135 | 25 | 275 |
| Strict: simulated success is inconclusive | 139 | 135 | 26 | 274 |
| Physical requirements count as blocked | 140 | 138 | 22 | 278 |
| Exclude runtime-rule violations | 140 | 133 | 27 | 273 |

The 135 main blocked cases comprise 92 missing tools, 20 missing credentials or
accounts, 10 safety restrictions and 13 unavailable-network cases in the offline
runtime. Four other unavailable-network cases are inconclusive under L2.

The 25 main inconclusive cases are excluded from decided accuracy, not silently
dropped:

| Reason | Cases |
|---|---|
| Missing skill files (10) | r053, r063, r078, r153, r154, r170, r185, r217, r250, r259 |
| Other (8) | r042, r047, r137, r169, r173, r234, r264, r268 |
| Unavailable network/service outside the offline runtime (4) | r122, r144, r176, r222 |
| Human or physical requirement (3) | r054, r171, r295 |

Strict adjudication additionally excludes r022 as simulated success. The
no-violations analysis excludes r039 and r046, listed in the frozen violation
record for attempted or actual installation outside the permitted work directory.
Those are historical executor violations; the continuation did not repeat them.

## Accuracy and errors

Counts are decisions on the 275 decided pairs per repeat. No verdict is not
correct and is not a refutation. Repeat 3 S includes the successor repairs.

| Repeat | S correct | D correct | S blocked caught | D blocked caught | S working refuted | D working refuted | S/D no verdict |
|---|---:|---:|---:|---:|---:|---:|---:|
| r1, original model | 228/275 (82.91%) | 230/275 (83.64%) | 111/135 | 101/135 | 20/140 | 11/140 | 5 / 1 |
| r2, original model | 228/275 (82.91%) | 236/275 (85.82%) | 109/135 | 103/135 | 20/140 | 7/140 | 3 / 0 |
| r3, mixed S | 230/275 (83.64%) | 232/275 (84.36%) | 110/135 | 102/135 | 18/140 | 10/140 | 5 / 0 |
| Pooled | 686/825 (83.15%) | 698/825 (84.61%) | 330/405 | 306/405 | 58/420 | 28/420 | 13 / 1 |

| Pooled metric | S, rate [Wilson 95% interval] | D, rate [Wilson 95% interval] |
|---|---|---|
| Accuracy | 83.15% [80.45, 85.55] | 84.61% [81.98, 86.91] |
| Blocked caught | 81.48% [77.41, 84.96] | 75.56% [71.14, 79.49] |
| Working refuted | 13.81% [10.84, 17.44] | 6.67% [4.65, 9.47] |
| No verdict | 1.58% [0.92, 2.68] | 0.12% [0.02, 0.68] |

These pooled denominators repeat the same pairs three times; their Wilson
intervals are the pre-registered descriptive calculation, not intervals based
on 825 independent skills. Repeat-level intervals are in the primary metrics.
The pre-registered paired r1 McNemar test gives 18 S-only correct cases,
20 D-only correct cases, **p = 0.871415**.

### Compaction and repair

| Repeat | Valid first reply | Located-error retries | Guarded repair jobs | Repairs accepted | Guard-rejected repairs | Final schema-valid |
|---|---:|---:|---:|---:|---:|---:|
| r1 | 279/300 | 21 | 151 | 151 | 0 | 300/300 |
| r2 | 283/300 | 17 | 146 | 144 | 2 | 300/300 |
| r3 | 274/300 | 26 | 140 | 140 | 0 | 300/300 |

No repair was malformed. Guard-rejected repairs retain the earlier refuted pack.
The S no-verdict cases are `DYNAMIC_TOPOLOGY` abstentions, not missing files or
schema failures. Final S verdict counts on all 300 pairs are:
r1 155 achievable / 140 impossible / 5 unknown;
r2 158 / 139 / 3; r3 157 / 138 / 5.

All 27 successor repairs parsed and passed the repair guard. Their final S
verdicts refute all 18 blocked and all six achieved cases; three cases remain
inconclusive. On those 24 decided cases S is correct in 18, D in 17; S wrongly
refutes 6/6 working cases against D's 3/6. The six false refutations are r113,
r224, r230, r243, r255 and r296. This is a selected subset of previously refuted
packs, not a random model comparison or a standalone successor-model evaluation.

### Repeat agreement and criteria

Agreement includes all 300 pairs, with no verdict as a separate category:

| Measure | S | D |
|---|---:|---:|
| Same verdict in all three repeats | 270/300 (90.0%) | 285/300 (95.0%) |
| Wilson 95% interval | [86.08%, 92.91%] | [91.92%, 96.95%] |
| Fleiss' kappa | 0.8699 | 0.9306 |
| r1/r2 agreement, original-model-only, descriptive | 277/300 | 290/300 |

S's three-repeat measure includes the model transition and cannot be interpreted
as pure same-model stability. Determinism for a fixed pack is a different claim.

| Pre-registered criterion | Observed result | Outcome |
|---|---|---|
| C1: S accuracy at least D minus 5 points | 83.15% vs 84.61%, gap -1.46 points | Pass |
| C2: S refutes no more working pairs | 58 vs 28 pooled decisions | **Fail** |
| C3: S agrees across repeats at least as often | 270 vs 285 pairs | **Fail** |
| C4: S median provider tokens at most 3x D | 466,942 / 336,436.5 = 1.388x | Pass, with harness caveat |

C1 is a descriptive pre-registered threshold, not a formal non-inferiority test.
No across-model r1 analysis is possible: only one model has a complete r1 run.

## Sensitivity analyses

All counts below pool the three repeats. Complete intervals and no-verdict rates
are in `analysis.json`; each sensitivity has its own inconclusive set above.

| Rule | S/D correct | S/D blocked caught | S/D working refuted |
|---|---|---|---|
| Main | 686/825 / 698/825 | 330/405 / 306/405 | 58/420 / 28/420 |
| Strict | 683/822 / 695/822 | 330/405 / 306/405 | 58/417 / 28/417 |
| Physical | 692/834 / 704/834 | 336/414 / 312/414 | 58/420 / 28/420 |
| No violations | 682/819 / 692/819 | 326/399 / 300/399 | 58/420 / 28/420 |

The direction of the accuracy and false-refutation comparison is unchanged.

## Runtime and repository slices

Pooled over repeats; intervals and no-verdict rates are in `analysis.json`.

| Runtime | Total / inconclusive pairs | S/D correct | S/D blocked caught | S/D working refuted |
|---|---|---|---|---|
| Developer sandbox | 110 / 14 | 246/288 / 259/288 | 63/81 / 60/81 | 20/207 / 8/207 |
| Offline workstation | 76 / 8 | 153/204 / 159/204 | 83/123 / 90/123 | 11/81 / 12/81 |
| Office assistant | 114 / 3 | 287/333 / 280/333 | 184/201 / 156/201 | 27/132 / 8/132 |

Every source repository is included below. `0/0` means no case of that class,
not a zero error rate. Repository names identify pinned source copies, not live
services contacted by this continuation.

| Repository | Pairs / inconclusive | S correct | D correct | Blocked caught, S / D | Working refuted, S / D |
|---|---|---:|---:|---|---|
| AgentCTO/claude-skills | 5 / 0 | 12/15 | 9/15 | 4/6 / 0/6 | 1/9 / 0/9 |
| CaliLuke/skills | 27 / 0 | 68/81 | 73/81 | 19/24 / 18/24 | 8/57 / 2/57 |
| K-Dense-AI/claude-scientific-skills | 15 / 2 | 36/39 | 39/39 | 33/36 / 36/36 | 0/3 / 0/3 |
| NVIDIA/skills | 25 / 3 | 55/66 | 59/66 | 38/45 / 41/45 | 4/21 / 3/21 |
| alirezarezvani/claude-skills | 12 / 1 | 29/33 | 23/33 | 12/15 / 8/15 | 1/18 / 3/18 |
| cloudflare/skills | 5 / 0 | 12/15 | 12/15 | 12/15 / 12/15 | 0/0 / 0/0 |
| coreyhaines31/marketingskills | 3 / 0 | 5/9 | 6/9 | 5/6 / 3/6 | 3/3 / 0/3 |
| davila7/claude-code-templates | 27 / 0 | 70/81 | 67/81 | 31/39 / 27/39 | 3/42 / 2/42 |
| getsentry/skills | 2 / 0 | 6/6 | 6/6 | 0/0 / 0/0 | 0/6 / 0/6 |
| github/awesome-copilot | 25 / 3 | 60/66 | 57/66 | 30/30 / 21/30 | 6/36 / 0/36 |
| glebis/claude-skills | 30 / 7 | 59/69 | 64/69 | 38/48 / 43/48 | 0/21 / 0/21 |
| jeremylongshore/claude-code-plugins-plus-skills | 27 / 1 | 66/78 | 66/78 | 25/27 / 21/27 | 10/51 / 6/51 |
| meetrais/claude-agent-skills | 1 / 0 | 3/3 | 3/3 | 3/3 / 3/3 | 0/0 / 0/0 |
| muratcankoylan/Agent-Skills-for-Context-Engineering | 1 / 0 | 3/3 | 2/3 | 0/0 / 0/0 | 0/3 / 1/3 |
| neondatabase/agent-skills | 1 / 0 | 3/3 | 3/3 | 3/3 / 3/3 | 0/0 / 0/0 |
| sickn33/agentic-awesome-skills | 25 / 2 | 57/69 | 65/69 | 23/24 / 23/24 | 7/45 / 3/45 |
| trailofbits/skills | 11 / 1 | 25/30 | 27/30 | 13/18 / 15/18 | 0/12 / 0/12 |
| vtmocanu/skills | 29 / 4 | 50/75 | 54/75 | 23/39 / 24/39 | 9/36 / 6/36 |
| wshobson/agents | 29 / 1 | 67/84 | 63/84 | 18/27 / 8/27 | 6/57 / 2/57 |

The final frozen executor-copy metadata identifies 60 skills with scrubbed code,
not the earlier draw's count of 40; no binary file was withheld. Seven of the
60 are inconclusive. On the other 53, pooled S accuracy is 134/159 (84.28%)
against D's 125/159 (78.62%); blocked caught is 92/111 vs 85/111; working
refuted is 6/48 vs 8/48. This slice is descriptive and not independently sampled.

## Tokens and time

Provider tokens include uncached input, output, cache reads and cache writes,
summed across every recorded attempt. Copilot's input total includes caches;
the continuation normalizes it to uncached input before adding the cache columns.
The GPT-2 BPE proxy counts only frozen system/user prompts and reply files,
including retry and repair prompts, not the agent harness.

| Per-decision measure, all 900 decisions per arm | S median [IQR] | D median [IQR] |
|---|---|---|
| Provider tokens, including cached tokens | 466,942 [362,164.25, 795,606.25] | 336,436.5 [332,562, 342,644.25] |
| Provider output tokens | 15,543 [9,284, 23,165.5] | 1,559.5 [1,301, 2,143.5] |
| GPT-2 BPE prompt plus reply tokens | 7,672.5 [4,528.5, 10,779.25] | 2,541.5 [1,739.75, 3,691] |
| Summed agent wall time, seconds | 91.877 [59.5408, 132.6535] | 13.937 [11.9912, 18.0165] |

The provider-token ratio is **1.388x**, but the prompt/reply BPE ratio is
**3.019x**. C4 uses provider usage and passes; the proxy would not meet a
three-times threshold. Tokens are not subscription charges or monetary costs.
The new harness is smaller than the original one, so the pooled cost comparison
is not a controlled single-harness model comparison.

| Repeat | S median provider tokens | D median provider tokens | S/D median seconds |
|---|---:|---:|---|
| r1 | 704,097 | 335,909.5 | 93.1145 / 13.7905 |
| r2 | 598,815.5 | 337,053 | 92.1735 / 13.9895 |
| r3, mixed S | 433,137 | 336,762 | 90.7635 / 14.0795 |

Per-repeat IQRs are in `analysis.json`. Time is the sum of an individual
decision's attempt durations, not elapsed time for concurrent benchmark batches.

| Agent arm | Attempt records | Uncached input | Output | Cache reads | Cache writes |
|---|---:|---:|---:|---:|---:|
| S, including original failures and continuation | 1,824 | 15,010 | 15,909,659 | 422,195,942 | 101,191,877 |
| D | 903 | 9,078 | 1,763,122 | 253,156,772 | 53,001,413 |
| Execution, separate from S/D cost | 300 | 11,084 | 3,857,014 | 399,732,509 | 24,033,869 |
| Adjudication, separate from S/D cost | 140 | 3,820 | 631,186 | 126,113,738 | 11,135,048 |

The 28 new sessions account for 1,109,634 provider tokens, including caches,
and 480.792 summed seconds. The ledger contains 406 original synthetic-error-only
records with zero token usage, 14 records with both original-model and synthetic
error entries, and one record without reported usage. The sentinel is not
evidence of an additional serving model. Provenance-separated totals remain in
`analysis.json`; no failed attempt was silently removed.

The original overhead-probe transcripts are not present in the transferred
evidence. Therefore the planned overhead-subtracted token estimate is **not
available**; the approximate 60,000-token harness description is not substituted
for a measurement. The raw provider and explicit prompt/reply proxy measurements
above are reported instead.

### Deterministic checker

For each of 900 final S packs, the median of seven sequential local checks was
measured. Across these pack medians: **12.26 ms median, 52.61 ms p90, 440.58 ms
maximum**. This is static validation time, not runtime verification or the
front-end's model-call time. Checks were not parallelized.

Scoring host: Python 3.13.17, Z3 5.1.0, 22 logical CPUs; GPT-2 encoding through
tiktoken 0.9.0. The encoding is the planned GPT-2 vocabulary, but this library
version differs from the plan's stated 0.14.0. Timings are local to this host,
not measurements from the original execution machine.

## Interpretation and limits

S's higher blocked recall comes with substantially more false refutations and
less repeat agreement than D. A sound refutation of a formal pack does not prove
that an untrusted compaction faithfully represented the skill. These results do
not extend the checker's guarantee to natural-language intent.

The mixed successor repairs, changed harness, selected continuation subset,
dependent pooled repeats, execution/adjudication by the same model family,
scrubbed resources and 25 inconclusive main cases limit generalization. The
same-model r1 comparison and all sensitivity outcomes remain visible rather than
being replaced by the pooled headline. No model calls were made after the truth
was restored.
