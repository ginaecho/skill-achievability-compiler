# Compaction reliability and baselines (experiment R)

Plan: `runs/20261015_review_response/PLAN.md` "Experiment R", written before any model call.
Run: `runs/20261015_reliability/`; every number is in its `metrics.json`, rows in `results.json`.
The set3 validation of the compaction fixes (P2g against P2g+, Rdet, P2g+ ∪ Rdet, D) is in the
section "set3: P2g against P2g+" below; its run is `runs/20261015_set3/`.

## Question

The reviewers asked three things about LLM compaction (natural-language skill to pack):

1. Is it reliable? Does the reply pass the schema gate, and do repeated samples give the
   same pack and the same verdict?
2. Does the pack buy accuracy? Is the full checker better than asking the model for a
   verdict directly (D), than a plain planner on the capability layer (P), or than a lint
   that only reads the runtime bindings (T)?
3. Is the pack faithful to the source document? (Blind judge, R5 below.)

## Set

`benchmark/claude_env/set2`: 100 real documents (70 SKILL.md, 30 agent.md) from public
repositories, pinned by commit and sha256 (all 100 hashes re-checked by `prepare`), drawn by
seed 20261004. Truth: 31 BLOCKED, 69 ACHIEVABLE (`set2/truth/c*.json`). Mapping: BLOCKED ->
IMPOSSIBLE, ACHIEVABLE -> ACHIEVABLE.

Two honest limits of this set:

- **The truth labels are requirement-availability labels, not execution outcomes.** Blind
  annotators listed each document's hard requirements and checked each one by read-only
  probes in a Claude Code cloud session. A label says whether every hard requirement is
  available in that session, not whether an agent completed the task.
- **The set was used once before**, to score the deterministic reader `skillc reach --claude`
  (commit 5c6fe79d, `benchmark/claude_env/REPORT.md`). No LLM compaction had run on it and
  no prompt was written after reading it, so the LLM arms are blind on it.

## Runtime

`src/skillc/data/runtimes/claude-code-cloud.json`, a transcription of the session the truth
was verified in: Linux x86_64, no GPU, no Docker daemon; egress through an allow-list proxy
(PyPI, npm, GitHub, Ubuntu, NuGet and the Go proxy open; other hosts refused, for example
huggingface, Microsoft Learn/Azure, Cloudflare, Expo, Neon, NVIDIA); the tools of
`session/tools.json` grouped into 14 runtime tools (bash, read, write, edit, web_fetch,
web_search, ask_user, agent, skill, tasks, artifact, send_user_file, push_notification,
mcp_resources); one tool per connector of `session/connectors.json` with its operations
(github, notion, google_drive, jam, mem, bigdata_com, etoro, claude_docs) and one granted
account resource per connector. Every arm got this manifest and nothing else about the session. It was written from REPORT.md's "Environment" paragraph and the two session files only;
no case-level result was used.

## Arms

| arm | what | model | samples |
|---|---|---|---|
| P2g | runtime-bound CE compaction, parse, bind (`prune=False`, no library), check; one located-error retry; one counterexample repair with the `repair_violations` guard | gpt-5.4 | 5 per document |
| P2g-x | the same | DeepSeek-V4-Pro | 1 |
| D / D-x | direct verdict from document + manifest (`direct_messages`), JSON | gpt-5.4 / DeepSeek-V4-Pro | 1 each |
| skillc | `check(pack)` on each final P2g pack (goal label) | none | per pack |
| P | `skillc.baselines.planner_only`: delete-relaxed STRIPS fixpoint from `init_true`, numeric comparisons free, no protocol, roles, messages or typing; IMPOSSIBLE iff the goal is unsatisfiable with unreachable atoms pinned false | none | per pack |
| T | `skillc.baselines.tool_lint`: IMPOSSIBLE iff a Tool the protocol invokes was withdrawn or blocked by the binder | none | per pack |

## Results

### Schema gate (P2g arms; valid = parses, passes `validate_pack` and binds)

| arm | samples | valid first | valid after retry | retried | repair rounds | repair kept | repair rejected by guard | repair invalid |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| P2g (gpt-5.4) | 500 | 339 (0.678, CI 0.64–0.72) | 462 (0.924, CI 0.90–0.94) | 161 | 178 | 157 | 6 | 15 |
| P2g-x (DeepSeek) | 100 | 6 (0.06) | 16 (0.16) | 94 | 6 | 4 | 1 | 1 |

D and D-x: 100/100 valid JSON verdicts each. The commonest first-round errors for gpt-5.4 are a Tool without `via` (36), a comma list
where CE wants one statement (22), and repeated `adds` / `requires` clauses (16 each).
DeepSeek mostly breaks a Tool statement over several lines (45 of 94 first errors), which CE
does not allow; the retry seldom fixes it.

### Verdict accuracy, sample 0 (decided = ACHIEVABLE or IMPOSSIBLE; UNKNOWN and INVALID not scored)

| arm | decided | correct | accuracy | 95% CI | BLOCKED recall (of 31) | false refutations (of 69) | UNKNOWN | INVALID |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| skillc | 88 | 60 | 0.682 | 0.58–0.77 | 7 (0.23) | 11 (0.16) | 0 | 12 |
| P | 88 | 60 | 0.682 | 0.58–0.77 | 6 (0.19) | 10 (0.14) | 0 | 12 |
| T | 88 | 68 | 0.773 | 0.67–0.85 | 5 (0.16) | 1 (0.01) | 0 | 12 |
| D (gpt-5.4) | 97 | 77 | 0.794 | 0.70–0.86 | 29 (0.94) | 18 (0.26) | 3 | 0 |
| D-x (DeepSeek) | 98 | 67 | 0.684 | 0.59–0.77 | 29 (0.94) | 29 (0.42) | 2 | 0 |
| skillc on P2g-x | 16 | 8 | 0.500 | 0.28–0.72 | 1 | 4 | 0 | 84 |
| P on P2g-x | 16 | 10 | 0.625 | 0.39–0.82 | 1 | 2 | 0 | 84 |
| T on P2g-x | 16 | 12 | 0.750 | 0.51–0.90 | 1 | 0 | 0 | 84 |

Always answering ACHIEVABLE scores 0.69 on all 100. Of skillc's 11 false refutations, 8
are GOAL_UNSAT (the pack's own effects cannot reach its Goal) and 3 BLOCKED_GUARD. Its 7
correct refutations are 3 MISSING_CAPABILITY, 2 BLOCKED_GUARD, 2 GOAL_UNSAT.

All five P2g samples pooled (500 rows, 462 decided):

| arm | decided | accuracy | 95% CI | BLOCKED recall | false refutations (of 345) | per-sample accuracy |
|---|---:|---:|---|---:|---:|---|
| skillc | 462 | 0.669 | 0.62–0.71 | 0.29 | 56 | 0.68, 0.61, 0.66, 0.75, 0.64 |
| P | 462 | 0.662 | 0.62–0.70 | 0.25 | 52 | 0.68, 0.61, 0.67, 0.72, 0.63 |
| T | 462 | 0.749 | 0.71–0.79 | 0.20 | 5 | 0.77, 0.74, 0.73, 0.77, 0.73 |

### Cross-sample agreement (P2g, 5 samples, 100 documents)

| metric | value |
|---|---|
| all five verdicts agree (INVALID counted as a label) | 39/100 = 0.39 (CI 0.30–0.49) |
| all five agree, among the 75 documents with five valid packs | 0.51 |
| Fleiss' kappa over verdicts (skillc) / P / T | 0.26 / 0.26 / 0.38 |
| all five agree, P / T | 0.42 / 0.66 |
| mean pairwise Jaccard of Tool names (869 valid pairs) | 0.27 |
| mean pairwise Jaccard of goal atoms | 0.22 |
| same IMPOSSIBLE witness, documents with 2+ IMPOSSIBLE samples | 4/29 = 0.14 |

Witness: the missing runtime tools and resources the binder found, else reason + frontier.
Low name Jaccard is partly expected (identifiers are coined each time); verdict disagreement is not.

### Cross-model agreement

| pair | n | Cohen's kappa |
|---|---:|---:|
| P2g s0 vs P2g-x, verdict labels incl. INVALID | 100 | -0.03 |
| same, both valid | 13 | -0.05 |
| D (gpt-5.4) vs D-x (DeepSeek) | 100 | 0.54 |

With 84 invalid DeepSeek packs, the P2g cross-model number says only that DeepSeek did not
produce valid CE, not how two valid compactions compare.

### Paired comparisons (exact McNemar on cases both arms decided; b = first right, second wrong)

| pair | paired cases | b | c | p | first acc | second acc |
|---|---:|---:|---:|---:|---:|---:|
| skillc vs D | 85 | 13 | 24 | 0.099 | 0.68 | 0.81 |
| skillc vs P | 88 | 1 | 1 | 1.0 | 0.68 | 0.68 |
| P2g vs P2g-x (skillc) | 13 | 4 | 2 | 0.69 | 0.69 | 0.54 |
| D gpt-5.4 vs D DeepSeek | 95 | 14 | 5 | 0.064 | 0.80 | 0.71 |
| skillc vs T (extra, not pre-registered) | 88 | 3 | 11 | 0.057 | 0.68 | 0.77 |

### Model calls

1239 calls: 2,284,469 uncached input tokens, 3,437,184 cached input tokens, 557,233 output
tokens. P2g 839 calls (500 + 161 retries + 178 repairs), P2g-x 200, D 100, D-x 100.

## Pre-registered criteria

| criterion | rule | value | met |
|---|---|---|---|
| R1 | schema-gate pass after retry >= 0.95 | 0.924 | **not met** |
| R2 | all-five-agree >= 0.80 and Fleiss' kappa >= 0.6 | 0.39, 0.26 | **not met** |
| R3 | false refutations <= 10% of ACHIEVABLE documents | 11/69 = 0.159 | **not met** |
| R4 | skillc decided accuracy within 5 points of D, or better | 0.682 vs 0.794 (-11.2) | **not met** |
| R5 | fidelity F1 and F4 >= 0.85 yes | F1 0.909, F4 0.898 (88 items) | **met** |

R4 not met: as the plan says, on this set the pack does not buy verdict accuracy, and the
case for it rests on the witness and the deterministic re-check, as the I2L benchmark
already concluded.

## What the numbers say

- gpt-5.4 writes valid CE for 68% of first replies and 92% after one retry; DeepSeek-V4-Pro
  writes valid CE for 16% after retry. The CE surface is not robust across model families.
- The compaction is not stable. Five samples of the same prompt give the same verdict on
  39 of 100 documents and share about a quarter of their Tool names and goal atoms. The
  checker is deterministic, so this variance is the compaction's.
- The protocol layer adds nothing to verdict accuracy here: skillc and P disagree on the
  verdict's correctness on 2 of 88 documents. Almost every refutation is decided by
  capabilities and goal, not by order or typing.
- The plain tool lint T is the most accurate pack-based arm (0.77 decided, 1 false
  refutation). Most of skillc's false refutations are GOAL_UNSAT on packs whose own effects
  do not reach their Goal: compaction slips the repair round did not fix.
- Every pack-based arm misses most BLOCKED documents (recall 0.16–0.29): the compactor
  binds the operation to `bash` or `web_fetch` without noting the refused host, the GPU or
  the account, so nothing is withdrawn or blocked. The direct verdict finds 29 of 31, at the
  price of 18 (gpt-5.4) and 29 (DeepSeek) false refutations.
- D (gpt-5.4) is the most accurate arm on decided cases; the gap to skillc (0.79 vs 0.68)
  is not significant at the 5% level on 85 paired cases (p = 0.10).

## What they do not say

- Nothing about execution: the labels are availability labels from read-only probes.
- Nothing about other runtimes or document populations (100 documents, one manifest).
  Fidelity (R5) is one judge family's reading of 88 packs, with the caveats in its section.
- The arms see the same manifest, but D answers from the whole document while P2g must
  first write every requirement as a binding; a requirement the compactor does not write is
  invisible to skillc, P and T alike.

## Caveats

- Shared code moved during the run. `checker.py`, `pack.py` and `frontend/runtime.py` were
  being edited by another agent; their hashes at `prepare` and at `score` differ (both are in
  `metrics.json`). Verdicts are from the checker at score time; the decision to send a repair
  prompt was taken by the checker at run time. `score` applies every round-3 reply on disk.
- The harness `scripts/reliability.py` was changed after `prepare` but before any scored
  call: case/sample filters for the smoke test, and z3 work moved out of the worker threads
  (z3 crashed with an AST assertion when called from several threads). No prompt changed;
  every prompt matches its sha256 in `frozen.json`. Smoke-test replies (c001 all arms; c002,
  c009, c011 P2g s0) were produced by the same prompts and are part of the run.
- Two earlier run processes died (exit 127, then the z3 crash); `run` only executes missing
  outputs, so no finished call was repeated; calls in flight when a process died were sent again and only the finished one is counted.
- The manifest states "other hosts are refused" as REPORT.md and the PLAN do. The annotators
  found at least one host outside that list open (releases.hashicorp.com, in c001's truth).
- 12 of 100 sample-0 packs are invalid, so the judge has 88 items, not 100.
- gpt-5.4 and DeepSeek ran with the deployment's default sampling and reasoning settings
  (no temperature or effort is set by the provider client).

## Fidelity (blind judge, R5)

Items: `runs/20261015_reliability/judge/items/<case>.json`, 88 documents (P2g sample 0 with a
valid pack): the source text, the final pack rendered as CE with its bindings, the runtime and
the rubric F1..F5; no verdict, truth or score. Judges: Claude sub-agents of this session (a
model family that neither wrote the packs nor the truth labels), following `judge/README.md`.
Scores are in `judge/scores/`; a second judge scored the 18 cases of `judge/second_judge.json`
into `judge/scores2/` without reading the first judge's files. Numbers from `metrics.json`
(`fidelity`).

| item | yes | no | unclear | yes rate | 95% CI |
|---|---:|---:|---:|---:|---|
| F1 no invented Tool | 80 | 5 | 3 | 0.909 | 0.83–0.95 |
| F2 no omitted mandatory step | 55 | 31 | 2 | 0.625 | 0.52–0.72 |
| F3 the Goal states the deliverable | 64 | 16 | 8 | 0.727 | 0.63–0.81 |
| F4 no invented ordering | 79 | 6 | 3 | 0.898 | 0.82–0.95 |
| F5 bindings plausible | 60 | 18 | 10 | 0.682 | 0.58–0.77 |

Second judge, 18 cases:

| item | agree | Cohen's kappa |
|---|---:|---:|
| F1 | 17/18 | 0.64 |
| F2 | 13/18 | 0.32 |
| F3 | 16/18 | 0.70 |
| F4 | 15/18 | -0.08 |
| F5 | 12/18 | 0.42 |
| pooled (90 judgements) | 0.81 | 0.47 |

R5 (F1 and F4 >= 0.85 yes) is **met**: 0.909 and 0.898. The packs seldom invent a Tool or an
order. What they get wrong is the other way round: a third of them omit a mandatory step
(F2 0.63), a quarter misstate the deliverable (F3 0.73), and a third have a binding the judge
found implausible or could not judge (F5 0.68).

Caveats the judges reported, and what follows from them:

- One judge reported that it could not read the middle of some long items and took the
  Tools on trust there. F1 and F2 on those items rest on the parts it read, so they lean
  towards yes.
- Two items had empty packs (no Tool and no protocol step to judge), which makes F1 and F4
  trivially yes for them.
- The F4 kappa is negative while raw agreement is 15/18: both judges said yes on almost every
  item, so chance agreement is high and the three disagreements dominate kappa. The F4
  yes-rate is a one-judge number; the second judge does not confirm it item by item.
- Both judges are of one model family (Claude) and judged against the rubric's wording; this
  is not a human fidelity study.

## set3: P2g against P2g+

Plan: `runs/20261015_review_response/PLAN.md`, Addendum B (fixes F-a to F-f, criteria B1 to B3),
Addendum C (the arms below, criteria C1 to C3) and the two amendments (F-f, F-h), all written
before any set3 model call. Run: `runs/20261015_set3/`. Every number below is in its
`metrics.json`; one row per case, arm and sample is in `results.json`.

### Set

`benchmark/claude_env/set3`: 100 documents (70 SKILL.md, 30 agent.md) drawn with seed
20261005 and disjoint from sets 1 and 2 (`select_cases.py --exclude` both), pinned by commit
and sha256. Ten blind annotators (Claude sub-agents, ten documents each) labelled them against
the `claude-code-cloud` manifest text with `set3/RUBRIC.md`, without seeing skillc: 82
ACHIEVABLE, 18 BLOCKED. These are **judgement labels against the manifest text**, not labels
verified by probes in a live session as set2's are. They are weaker, and every number in this
section inherits that.

The working-tree copies of `set3/cases/*.md` have CRLF line ends; `cases.json` pins the LF
bytes. The harness checks the sha256 after reading CRLF as LF, which is also the text every
arm received (Python's `read_text`). All 100 match.

### Arms

| arm | what | model | samples |
|---|---|---|---|
| P2g | experiment R's method: `ce_runtime_messages(version="p2g")`, one located-error retry, one guarded repair, `bind_runtime(prune=False)` | gpt-5.4 | 3 |
| P2g+ | `ce_runtime_messages(version="p2g+")` (F-a to F-c, F-f; the `reply` tool), two located-error retries, one guarded repair, the rounds of `frontend.llm.compact_ce_rounds` | gpt-5.4 | 3 |
| Rdet | `env.manifest.refute_text(text, "claude-code-cloud")`: the deterministic requirement reader against the manifest, no model | none | 1 |
| P2g+ ∪ Rdet | per sample: IMPOSSIBLE if either refutes; ACHIEVABLE only if both say ACHIEVABLE; otherwise UNKNOWN | derived | 3 |
| D | direct verdict (`direct_messages`) | gpt-5.4 | 1 |

The parser tolerance F-h (grammar 1.4) applies to both P2g and P2g+. The manifest is the
current `claude-code-cloud.json`. It now has the additive fields Rdet reads (`egress_allow`,
`egress_deny`, `unavailable_programs`); the text the models see is the same as in experiment
R. Every round-1 prompt was frozen with its sha256 in `frozen.json` before the first call, and
every later prompt is recorded there with its sha256. No prompt changed after the freeze.
Smoke test: one document (c012, sample 0) for each arm, read by eye, then the full run. The
smoke-test replies come from the frozen prompts and are part of the run.

### Schema gate

| arm | samples | valid first | valid after 1 retry | valid after all retries | retried | repair rounds | repair kept | rejected by guard | repair invalid |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| P2g | 300 | 220 (0.733, CI 0.68–0.78) | 287 (0.957) | 287 (0.957, CI 0.93–0.97) | 80 | 114 | 108 | 3 | 3 |
| P2g+ | 300 | 185 (0.617, CI 0.56–0.67) | 255 (0.850) | 276 (0.920, CI 0.88–0.95) | 115 | 15 | 13 | 1 | 1 |

D: 100 of 100 valid JSON verdicts. The commonest first-round error for P2g+ is `not` inside a
branch assumption or a condition (43 of 115), which the grammar does not allow there. With its
second retry, P2g+ is still less often valid than P2g after one retry.

### Verdict accuracy, sample 0 (decided = ACHIEVABLE or IMPOSSIBLE)

| arm | decided | correct | accuracy | 95% CI | BLOCKED recall (of 18) | false refutations (of 82) | UNKNOWN | INVALID |
|---|---:|---:|---:|---|---:|---:|---:|---:|
| P2g | 94 | 64 | 0.681 | 0.58–0.77 | 7 (0.39, CI 0.20–0.61) | 20 (0.244) | 2 | 4 |
| P2g+ | 90 | 76 | 0.844 | 0.76–0.91 | 2 (0.11, CI 0.03–0.33) | 1 (0.012) | 1 | 9 |
| Rdet | 100 | 83 | 0.830 | 0.74–0.89 | 8 (0.44, CI 0.25–0.66) | 7 (0.085) | 0 | 0 |
| P2g+ ∪ Rdet | 93 | 75 | 0.806 | 0.71–0.87 | 8 (0.44, CI 0.25–0.66) | 8 (0.098) | 7 | 0 |
| D | 96 | 74 | 0.771 | 0.68–0.84 | 16 (0.89, CI 0.67–0.97) | 20 (0.244) | 4 | 0 |
| T on P2g (extra) | 96 | 81 | 0.844 | 0.76–0.90 | 3 (0.17) | 1 | 0 | 4 |
| T on P2g+ (extra) | 91 | 77 | 0.846 | 0.76–0.91 | 1 (0.06) | 0 | 0 | 9 |
| P on P2g (extra) | 96 | 65 | 0.677 | 0.58–0.76 | 6 (0.33) | 20 | 0 | 4 |
| P on P2g+ (extra) | 91 | 71 | 0.780 | 0.68–0.85 | 7 (0.39) | 12 | 0 | 9 |

Always answering ACHIEVABLE scores 0.82 on all 100. T and P are the baselines of experiment R,
computed on the same packs, and they are not pre-registered for set3. P ignores branch
assumptions (it is a fixpoint from `init_true`), so its refutations on P2g+ packs are partly
artefacts of F-a. Recall counts INVALID and UNKNOWN as misses, as in experiment R.

### Pooled over the three samples (300 rows per arm)

| arm | decided | accuracy | 95% CI | BLOCKED recall (of 54) | false refutations (of 246) | per-sample accuracy | per-sample recall | per-sample false refutations |
|---|---:|---:|---|---:|---:|---|---|---|
| P2g | 281 | 0.712 | 0.66–0.76 | 0.407 (CI 0.29–0.54) | 50 (0.203) | 0.68, 0.68, 0.78 | 0.39, 0.33, 0.50 | 20, 18, 12 |
| P2g+ | 270 | 0.830 | 0.78–0.87 | 0.074 (CI 0.03–0.18) | 2 (0.008) | 0.84, 0.83, 0.81 | 0.11, 0.11, 0.00 | 1, 1, 0 |
| P2g+ ∪ Rdet | 275 | 0.818 | 0.77–0.86 | 0.444 (CI 0.32–0.58) | 23 (0.093) | 0.81, 0.82, 0.82 | 0.44, 0.44, 0.44 | 8, 8, 7 |
| T on P2g (extra) | 287 | 0.836 | 0.79–0.87 | 0.167 | 3 | | | |
| T on P2g+ (extra) | 276 | 0.837 | 0.79–0.88 | 0.056 | 0 | | | |

Of the 47 IMPOSSIBLE union verdicts, Rdet alone gave 41, both gave 4 and P2g+ alone gave 2.

By kind, sample 0 (accuracy on decided cases / BLOCKED recall / false refutations):

| arm | 70 SKILL.md | 30 agent.md |
|---|---|---|
| P2g | 0.63 / 0.47 / 17 | 0.80 / 0.00 / 3 |
| P2g+ | 0.82 / 0.13 / 1 | 0.90 / 0.00 / 0 |
| Rdet | 0.81 / 0.53 / 6 | 0.87 / 0.00 / 1 |
| P2g+ ∪ Rdet | 0.78 / 0.53 / 7 | 0.86 / 0.00 / 1 |
| D | 0.79 / 0.93 / 13 | 0.72 / 0.67 / 7 |

### Cross-sample agreement (three samples, 100 documents)

| metric | P2g | P2g+ | P2g+ ∪ Rdet |
|---|---|---|---|
| all three verdicts agree (INVALID counted as a label) | 63/100 = 0.63 (CI 0.53–0.72) | 77/100 = 0.77 (CI 0.68–0.84) | 84/100 = 0.84 (CI 0.76–0.90) |
| all three agree, documents with three valid packs | 0.69 (of 90) | 0.94 (of 81) | 0.84 (of 100) |
| Fleiss' kappa over verdicts | 0.43 | 0.28 | 0.73 |
| mean pairwise Jaccard of Tool names | 0.29 (278 pairs) | 0.33 (258 pairs) | n/a |
| mean pairwise Jaccard of goal atoms | 0.20 | 0.29 | n/a |
| same IMPOSSIBLE witness, documents with 2+ IMPOSSIBLE samples | 1/20 = 0.05 | 1/1 | 12/15 = 0.80 |

P2g+'s kappa is lower than P2g's although its samples agree more often. Nearly every P2g+
verdict is ACHIEVABLE, so chance agreement is high, and its disagreements are mostly an
INVALID sample against two ACHIEVABLE ones. The union's agreement is mostly Rdet's, which is
deterministic and the same in all three samples.

### Paired comparisons (exact McNemar on cases both arms decided; b = first right, second wrong)

| pair | pairs | b | c | p | first acc | second acc |
|---|---:|---:|---:|---:|---:|---:|
| P2g vs P2g+, pooled (case, sample) | 258 | 18 | 43 | 0.0019 | 0.72 | 0.82 |
| P2g vs P2g+, sample 0 | 86 | 5 | 15 | 0.041 | 0.72 | 0.84 |
| P2g+ ∪ Rdet vs D, sample 0 | 89 | 13 | 11 | 0.84 | 0.81 | 0.79 |
| P2g+ ∪ Rdet vs D, pooled (D repeated) | 263 | 42 | 30 | 0.19 | 0.82 | 0.77 |
| P2g+ vs D, sample 0 | 86 | 17 | 11 | 0.34 | 0.85 | 0.78 |
| P2g+ vs D, pooled (D repeated) | 258 | 52 | 38 | 0.17 | 0.83 | 0.78 |

False refutations on the 82 ACHIEVABLE documents, P2g against P2g+ at the same sample index:
pooled, P2g alone 50, P2g+ alone 2, both 0 (exact McNemar p < 1e-6); sample 0, 20 against 1
(p = 2.1e-5). The pooled pairs are (case, sample). The three samples of one document are not
independent, so the pooled p-values are optimistic; the sample-0 rows are the clean test.

### Rdet

Rdet refutes 15 documents: 8 BLOCKED and 7 ACHIEVABLE. It leaves 56 requirements `unknown`
(hosts or programs the manifest does not mention), and an unknown requirement never refutes.

**C3: Rdet false refutations on documents whose truth lists no unavailable hard requirement.**
There are seven, and each is a reader bug. In every one the reader takes an optional,
alternative or example mention as a hard requirement:

| case | Rdet requirement | evidence line | what the truth says |
|---|---|---|---|
| c001 | `account:render_account` | line 169: `export RENDER_API_KEY="<YOUR_API_KEY>"` | Render API key and Render MCP are optional (`hard: false`); the deliverable is a render.yaml and a deeplink |
| c005 | `account:hcp_account`, `account:aws_account` | line 80: `export HCP_CLIENT_SECRET=...`; line 32: `amazon-ebs` | the task is to write the Packer template; HCP and AWS credentials are `hard: false` |
| c006 | `account:aws_account` | line 214: `AWS_SECRET_ACCESS_KEY = "..."` | a code-review skill; the key is in an example of a vulnerability, not a requirement |
| c027 | `daemon:docker`, `program:docker` | line 68: `docker pull aflplusplus/aflplusplus:stable` | Docker is one of three ways to get AFL++ (`hard: false`); the apt package is installable |
| c032 | `credential:FOUNDRY_API_KEY`, `account:llm_api_key`, `account:azure_account` | lines 506–531: BYOK provider examples | Copilot auth or a BYOK key is hard but `unknown`; the provider keys are `hard: false` alternatives |
| c047 | `platform:windows` | line 84: `msbuild` | a Windows build example; the target is clang/libFuzzer on Linux |
| c081 | `account:aws_account` | line 229: `AWS Lambda` | observability configuration is written, not deployed; vendor accounts are `hard: false` |

**Witness agreement.** For each Rdet refutation of a BLOCKED document: does the truth's
`blocking` list hold the same requirement? An automatic match (same kind after mapping
account to credential, plus a shared name token) finds 5 of 8. Read by hand, 6 of 8 name the
same requirement, 1 names the same service under a different kind, and 1 names something
different:

| case | Rdet | truth `blocking` | same requirement? |
|---|---|---|---|
| c011 | `egress:ai.azure.com`, `account:azure_account` | egress ai.azure.com; credential Azure CLI login; other Foundry project | yes (automatic: yes) |
| c012 | `account:llm_api_key` | credential `OPENAI_API_KEY`; egress api.openai.com | yes, the same key (automatic: no, the names share no token) |
| c013 | `credential:AZURE_OPENAI_AUDIO_API_KEY`, `account:azure_account`, `account:llm_api_key` | credential `AZURE_OPENAI_AUDIO_API_KEY`; egress Azure OpenAI; other deployment | yes (automatic: yes) |
| c021 | `account:azure_account` | credential Azure subscription login; egress management.azure.com | yes (automatic: yes) |
| c031 | `platform:macos` | platform macos-xcode | yes (automatic: yes) |
| c034 | `account:llm_api_key` | tool `image_gen` | no: the annotator blocked on the missing built-in image tool; the API key is the CLI fallback's |
| c040 | `account:aws_account` | credential aws-account; egress aws-iam-api | yes (automatic: yes) |
| c061 | `mcp:atlassian` | egress admin.atlassian.com; credential Atlassian admin account or token | same service, different kind (connector against credential and host) |

### Defect classes on P2g+'s remaining false refutations

P2g+ has 2 false refutations in 246 ACHIEVABLE samples. Both were read in the packs:

| class | count | cases |
|---|---:|---|
| D1 branch fact as `requires` | 0 | |
| D2 reply deliverable | 0 | |
| D3 received predicates | 0 | |
| D4 goal has labels or intermediate states | 0 | |
| D8 missing `needs` | 0 | |
| other | 2 | c043 s1: a fact decided twice, by a Tool's nondeterministic `picks` and again by branch assumptions, so no successor world fits both (BLOCKED_GUARD); c058 s0: the starting fact written as `Initially: \`authority_missing\`.` (a constraint) instead of `Initially true:`, so no initial world exists (BLOCKED_GUARD), and the repair kept the line |

Details: `runs/20261015_set3/defects.json`. D1 to D4 do not occur on set3. P2g's 50 pooled
false refutations were not classed; the criterion asks only about P2g+.

### Why P2g+ misses BLOCKED documents (read from the packs, not pre-registered)

P2g+ calls 44 of its samples on BLOCKED documents ACHIEVABLE. In 36 of those 44, a Tool
`via reply` adds a Goal atom, and 32 have branch assumptions. The packs show three
mechanisms:

- **The Goal moves into the reply.** A `via reply` Tool needs no resource and is never
  withdrawn, so a Goal it adds is reachable whatever the runtime lacks. c034 (image
  generation; the runtime has no image tool) binds `generate_image_builtin` `via reply`.
  c029 (needs `js_repl`) makes the Goal `workflow_guidance_delivered` via reply. On
  ACHIEVABLE documents the pattern is just as common (204 of 220 ACHIEVABLE samples), so it
  is the prompt's general reading of rule 9, not a reaction to BLOCKED documents.
- **Branch assumptions absorb the missing requirement.** c012 (needs `OPENAI_API_KEY`) writes
  `branch key_present (assuming api_key_present)`: the key is now a fact of the branch, so
  nothing needs a grant. F-a was meant for facts the user or the project decides. Here the
  model also applies it to a credential the runtime does not have.
- **D8 stays.** c017 (Docker) and c011 (an Azure host) bind the work to `bash` with `needs`
  limited to granted resources, as P2g does on set2.

These readings are post hoc, on the set they describe. They are a reason for a new fix and a
new blind set, not a change to this run's numbers.

### Model calls

1069 calls: 2,536,229 uncached input tokens, 3,018,112 cached input tokens, 507,931 output
tokens. P2g 494 calls (300 + 80 retries + 114 repairs); P2g+ 475 (300 + 160 retries + 15
repairs); D 100; Rdet none. No call failed; no 429 or 5xx retry was needed. Four concurrent
model calls, one process, and every parse, bind and check on the main thread.

### Criteria

| criterion | rule | value | met |
|---|---|---|---|
| B1 | P2g+ false refutations at most half of P2g's (same samples, exact McNemar) | pooled 2 against 50 (p < 1e-6); sample 0, 1 against 20 | **met** |
| B2 | P2g+ BLOCKED recall not more than 5 points below P2g's | pooled 0.074 against 0.407 (-33.3 points); sample 0, 0.11 against 0.39 | **not met** |
| B3 | fidelity F1 and F4 yes-rates of P2g+ higher than P2g's on the same 30 documents | F1 0.90 -> 0.60, F4 0.83 -> 0.90 | **not met** |
| B4 | finance agent | not part of this run | not run here |
| C1 | BLOCKED recall of P2g+ ∪ Rdet at least D's minus 5 points | 0.444 against 0.889 (-44.4 points) | **not met** |
| C2 | false refutations of P2g+ ∪ Rdet at most 10% | 23/246 = 0.093 pooled (sample 0: 8/82 = 0.098) | **met** |
| C3 | Rdet: zero false refutations on documents without an unavailable hard requirement | 7 (c001, c005, c006, c027, c032, c047, c081), all reader bugs | **not met** |

Addendum B says that if B1 fails, P2g+ is not adopted as the default. B1 is met, but B2 is
not: P2g+ removes false refutations by almost never refuting. Its false-refutation rate
(0.008) and its recall (0.07) are both close to those of an arm that always answers
ACHIEVABLE, and its decided accuracy (0.83) is about that baseline's 0.82. On this set, P2g+
is not a better refuter than P2g. It is a quieter one.

### What the numbers say

- The fixes of Addendum B remove the false refutations they were written for: none of D1 to
  D4 appears among P2g+'s refutations, and its false refutations fall from 50 to 2 of 246.
- They also remove most true refutations. P2g+ finds 4 of 54 BLOCKED samples where P2g
  finds 22. The packs show the cause: the `reply` tool and branch assumptions let a Goal be
  reached without the Tool that needs the missing resource.
- Rdet, which reads no model output, is the best single refuter here: 8 of 18 BLOCKED
  documents with 7 false refutations, all of them traceable to one reader weakness (optional,
  alternative and example mentions read as hard). It has no variance across samples.
- P2g+ ∪ Rdet is about as accurate as D on decided cases (0.81 against 0.79 at sample 0,
  p = 0.84) and has fewer than half of D's false refutations (8 against 20). But it finds half
  as many BLOCKED documents (8 against 16). C1 is far from met: on these labels, the direct
  verdict is still the arm that finds missing requirements.
- Schema-gate validity is lower for P2g+ than for P2g, even with the extra retry (0.92 against
  0.96). The longer prompt brings a new error (`not` inside assumptions and conditions).

### What they do not say

- The labels are judgement labels against the manifest text from ten annotators of one model
  family, not probe-verified. A BLOCKED label means an annotator read a hard requirement as
  unavailable from the manifest's words. Rdet reads the same words, which favours it.
- 18 BLOCKED documents is a small number: every recall interval is wide (sample 0, D 0.67–0.97,
  union 0.25–0.66).
- Fidelity (B3, below) went down on F1 and up on F4. Lower false refutations do not by
  themselves say that the P2g+ packs are more faithful, and on F1 they are less so.
- One model (gpt-5.4) writes every pack and D. Nothing here is about other models or
  runtimes.
- Nothing was tuned on set3. The post-hoc reading above needs a new blind set before any
  revision is scored.

### Fidelity judge for B3 (scored)

Three Claude sub-agents judged the 60 items blind (two primary judges, 30 items each; a second
judge on both variants of 6 cases). Yes-rates on the same 30 documents:

| item | P2g | P2g+ |
|---|---|---|
| F1 no invented Tool | 0.90 | **0.60** |
| F2 no omitted mandatory step | 0.63 | 0.67 |
| F3 Goal names the deliverable | 0.90 | 0.77 |
| F4 no invented ordering | 0.83 | **0.90** |
| F5 bindings plausible | 0.57 | 0.87 |

B3 is **not met**: F4 improved, F1 fell. The judges' reasons point at one cause: the universal
`reply` tool. P2g+ packs add steps such as "deliver guidance" or "confirm completion" `via
reply` that no sentence of the document asks for, and the judges count them as invented
Tools; several P2g+ Goals are then met by that reply step alone, which also lowers F3. F5 rose
because `reply` replaced bindings the judges had marked implausible (output delivered through
`ask_user`). Second judge: 12 items, raw agreement 0.85, pooled kappa 0.34 (small sample; F3
had no disagreement to estimate from). The rubric did not anticipate `reply`; a future rubric
should say whether a deliverable written in the answer counts as an instruction.

### Fidelity judge for B3 (how it was prepared)

`runs/20261015_set3/judge/items/<case>__p2g.json` and `<case>__p2gplus.json`: 30 documents,
the first 30 in sha256("set3-judge:" + case) order among the documents where both arms
produced a valid sample-0 pack. Five documents earlier in that order were skipped because one
arm had no valid pack (c076, c049, c047, c004, c051; listed in `judge/documents.json`). Each
item has the shape of experiment R's (case, kind, source text, the pack rendered as CE, the
runtime, the rubric). It holds no verdict, no truth and no text that names the arm; only the
file name carries the variant. The runtime lists `reply` for both variants. Instructions:
`judge/README.md`. The second judge scores both variants of the 6 cases in
`judge/second_judge.json` (c006, c009, c012, c060, c069, c094). Then
`python scripts/reliability.py judge-score runs/20261015_set3` fills `fidelity` and B3 in
`metrics.json`.

### Harness

`scripts/reliability.py` gained `prepare OUT --set set3`; `run`, `score`, `judge-prep` and
`judge-score` read `frozen.json["experiment"]` and dispatch to the set3 code. Experiment R's
code paths are unchanged in behaviour. Re-scoring a copy of `runs/20261015_reliability` with
the old and the new harness gives byte-identical `results.json` and packs; only the timestamp
in `metrics.json` differs.

```
python scripts/reliability.py prepare runs/NEW --set set3
env -u AZURE_SUBSCRIPTION_ID -u AZURE_TENANT_ID \
    AZURE_OPENAI_ENDPOINT="https://foundary-tzuc06.openai.azure.com/openai/v1" \
    python scripts/reliability.py run runs/NEW          # 4 concurrent calls; resumes
python scripts/reliability.py score runs/NEW            # deterministic
python scripts/reliability.py judge-prep runs/NEW
```

## Reproduce

```
python scripts/reliability.py prepare runs/NEW                     # freezes cases, manifest, prompts
env -u AZURE_SUBSCRIPTION_ID -u AZURE_TENANT_ID \
    AZURE_OPENAI_ENDPOINT="https://foundary-tzuc06.openai.azure.com/openai/v1" \
    python scripts/reliability.py run runs/NEW                     # Azure CLI login; 6 workers
python scripts/reliability.py score runs/NEW                       # deterministic, no model call
python scripts/reliability.py judge-prep runs/NEW
python -m pytest tests/test_baselines.py -q
```
