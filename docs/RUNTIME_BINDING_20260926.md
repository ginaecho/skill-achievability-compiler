# Improving IMPOSSIBLE accuracy: runtime-bound compaction (P1–P3)

Follow-up: the tool-policy library test and the pooled P2g result are in
[`TOOL_POLICY_LIBRARY_20260926.md`](TOOL_POLICY_LIBRARY_20260926.md).

Follow-up to `CONTROLLED_ENGLISH_AB_20260926.md`. That A/B found that most
IMPOSSIBLE verdicts on real skills were false: the executor could do the job.
The question here: *why were missing tools not detected as missing
capabilities, and what fixes it?* Every claim below is scored against blind
execution: an agent really attempted each skill in the sandbox.

Plans were written before the runs they govern:
`runs/20260926_ce_ab/RUNTIME_BINDING_PLAN.md` (P1/P2) and
`runs/20260926_ce_runtime_p1/P3_PLAN.md` (P3 and the held-out test).

## Main conclusion

1. **The environment was the cause.** The compactor was told the runtime only
   in prose, with no tool manifest. Rule 1 then forbade inventing tools. So the
   model had no correct way to say "this step needs a tool the runtime does
   not have".
2. **Binding every Tool to a closed runtime manifest (P1) is what improves
   accuracy.** Each Tool is bound with `via <runtime tool>` and
   `needs <resource>`, and the binder is deterministic. On 40 fresh held-out
   skills, all executed, runtime-bound CE:
   - raises recall of truly impossible skills from 3/14 (original JSON) to
     9/14 (P1) or 8/14 (P2g);
   - costs at most one extra false rejection;
   - raises decided accuracy from 24/36 to 29/36.

   The difference is not significant at this sample size (McNemar p = 0.18 to
   0.23).
3. **On an unbiased sample, the original method's main error is missed
   impossibles, not false rejections.** The A/B dev set was built from rejected
   skills, so it overstated the false-rejection problem.
4. **Two-level goals (P3) buy precision at the cost of recall.** On the
   held-out set: 0 false rejections and 6/6 precision, but recall 6/14. That
   fails pre-registered criterion 3 (recall no more than one below P2g's
   8/14). The lost cases are skills whose purpose *is* the deployment; the
   model filed the deployment as the Live goal.
5. **Two deterministic safeguards are sound and kept:**
   - the repair guard (Goal, Live goal and `needs` must survive a repair);
   - runtime branch pruning (it fixes a real interaction with the T-Comm
     typing rule).

## Methods compared

| id | what the LLM does | what is deterministic |
|---|---|---|
| json | original JSON compaction (A/B arm) | checker |
| P1 | NL → CE with `via`/`needs` against the `developer-sandbox` manifest; one located-error retry | parse, bind (withdraw / block), check |
| P2 | P1, plus one counterexample-guided repair of refuted cases | the refutation that is fed back |
| P2g | P2 | plus the **repair guard**: a repair is rejected if the Goal changes or a surviving Tool loses a `needs` |
| P3 | P1 prompt with rule 10 replaced by **two goal levels** (`Goal:` core deliverable, optional `Live goal:`); repair as P2g | plus **branch pruning**; verdict = core Goal |

- **Branch pruning.** The whole-session typing judgment quantifies over every
  branch of a choice. A skippable branch that contains a runtime-blocked Tool
  therefore made the protocol NON_CONFORMANT. That is why P2's "make it
  skippable" repair could not work. The binder now prunes branches of the
  agent's own non-external choices that only a withdrawn or blocked Tool could
  run, as long as a runnable branch remains. External choices are never
  pruned.
- **Repair guard.** It was motivated by two observed violations of the repair
  prompt: render-deploy rewrote its Goal, and web-perf dropped a `needs`.

## Labels

- **L1:** only `missing_tool_in_runtime` confirms an IMPOSSIBLE verdict.
- **L2:** the manifest explicitly lacks accounts, credentials, publishing and
  connectors, so `needs_credentials_or_account` and
  `forbidden_by_safety_rules` also confirm. `network_or_service_unavailable`,
  `needs_human_or_physical` and `skill_underspecified` stay inconclusive.
- **Primary scheme:** L2.

## Evaluation B: held-out (confirmatory)

- **Sample:** 40 skills never compacted or inspected, taken as the next 40 in
  the A/B's own stratified order (`python scripts/compare_heldout.py`,
  `runs/20260926_heldout_comparison.json`).
- **Executions:** every skill was executed regardless of verdict.
- **Labels (L2):** 22 achieved, 14 impossible, 4 inconclusive.

| method | IMPOSSIBLE | precision | recall | false rejections | decided accuracy | vs json (better/worse, p) |
|---|---|---|---|---|---|---|
| json (original) | 4 | 3/4 | 3/14 | 1/22 | 24/36 | — |
| P1 | 12 | 9/11 | **9/14** | 2/22 | **29/36** | 8/3, 0.23 |
| P2g | 9 | 8/9 | 8/14 | 1/22 | **29/36** | 7/2, 0.18 |
| P2g + pruning | 9 | 8/9 | 8/14 | 1/22 | 29/36 | 7/2, 0.18 |
| P3 (no repair) | 7 | 7/7 | 7/14 | **0/22** | **29/36** | 6/1, 0.13 |
| P3 | 6 | **6/6** | 6/14 | **0/22** | 28/36 | 6/2, 0.29 |

L1 (missing tool only): 4 confirmed impossibles. json catches 0, P1–P3 each
catch 1.

**Sensitivity.** One executor, notion-meeting-intelligence, violated its
protocol (see Incidents); it is labelled `forbidden_by_safety_rules`. Excluding
it:

| method | decided accuracy |
|---|---|
| json | 23/35 |
| P1 | 28/35 |
| P2g | 28/35 |
| P3 (no repair) | 28/35 |
| P3 | 27/35 |

Every method rejected that skill, so the ranking is unchanged.

**P3 against its pre-registered criteria (held-out):**

1. Fewer false rejections than json: 0 vs 1. **Met.**
2. L2 precision at least json's and at least P2g's: 6/6 vs 3/4 and 8/9. **Met.**
3. Recall no more than one below P2g's: 6/14 vs 8/14. **Not met.**
4. Labelled scenarios 16/16 with 0 false positives. **Met** (Evaluation A).

## Evaluation A: dev + control (development, not independent)

The same 47 dev skills, 50 control skills and 32 labelled scenarios as P1/P2.
P3 was designed after inspecting these, so the numbers are optimistic.

| method | dev IMPOSSIBLE | L2 precision | false rejections (30 achieved) | control rejections: false / L2-correct / inconclusive |
|---|---|---|---|---|
| json | 28 | 7/24 | 17/30 | — (the control set is json-ACHIEVABLE by construction) |
| P1 | 23 | 9/22 | 13/30 | 22: 11 / 11 / 0 |
| P2 | 17 | 8/17 | 9/30 | 18: 7 / 11 / 0 |
| P2g | 18 | 9/18 | 9/30 | 18: 7 / 11 / 0 |
| P2g + pruning | 17 | 9/17 | 8/30 | 18: 7 / 11 / 0 |
| P3 | 8 | 7/8 | **1/30** | 15: 5 / 10 / 0 |

- **Labelled scenarios:** 16/16 impossible refuted, 0 false refutations, for
  every method.
- **Recall of true rejections.** P3 lost three L2-true rejections on dev
  (eas-hosting, neon-auth, render-deploy). All three are deployment skills
  where P3's *live* verdict is still IMPOSSIBLE. Reporting both levels keeps
  the warning; the core verdict alone loses it.
- **L1-correct rejections.** Two dev skills confirmed as missing-tool
  (cli-exercise-exact, cli-exercise-explore) have been ACHIEVABLE since P1 in
  every runtime-bound method. The model binds the helper-driven execution
  step (`execute_case`) `via bash`, but the executor found the required
  Go/Tuistory helper absent. The manifest cannot catch a binding like that.
  Pre-registered criterion 2 therefore holds only with this explanation.

## Why the dev and held-out pictures differ

The dev set consists of skills that an A/B arm had *rejected*. On it, the
dominant error is false rejection, and every step that rejects less looks
good. The held-out set is an unbiased sample. There, the original method
rejects almost nothing and misses most true impossibles. Runtime binding
fixes that, and P3's extra caution gives back some of the gain.

## Recommendation

- **Default: P2g.** Runtime-bound CE with one guarded repair, pruning on,
  reporting **both** the core and live verdicts. It has the best recall at
  near-best precision.
- **Next pre-registered step (not run):** the "live-aware" decision rule.
  Report IMPOSSIBLE when the core verdict is IMPOSSIBLE, or when the live
  verdict is IMPOSSIBLE and the skill declares no core artifact beyond the
  live effect. It needs its own fresh held-out set; this one is spent.
- **Power:** n = 40 cannot separate the runtime-bound variants. About 150
  executed skills would be needed to detect a 10-point accuracy difference.

## Incidents during execution (reported, not hidden)

- **Notion write.** The executor for `openai__skills__notion-meeting-intelligence`
  used the session's Notion connector, which its prompt forbids, and created
  and updated a page in the user's workspace ("Sprint Planning Pre-Read: Q4
  Sprint 14 Kickoff"). The page was left untouched pending the user's
  decision. It is labelled `forbidden_by_safety_rules`, and a sensitivity
  analysis is given above.
- **Crash file in the repository root.** A fuzzing executor (ruzzy or libafl)
  wrote a 2-byte libFuzzer crash file there. It was moved out and never
  committed.
- **System packages.** The ruzzy executor installed a system package
  (`libclang-rt-18-dev`) with apt-get.
- **Disk cleanup.** The train-sentence-transformers executor cleared disk
  space it did not identify. Tracked files and earlier results were verified
  intact.
- **Stalled batch.** One compaction batch stalled; it was stopped and re-run
  from the same frozen prompts.

## Reproduction

```
python scripts/benchmark_ce_runtime.py prepare OUT --method ce_rt|ce_lv|json [--cases heldout]
python scripts/benchmark_ce_runtime.py retry OUT     # after round-1 replies
python scripts/benchmark_ce_runtime.py repair OUT    # CE methods, after retries
python scripts/benchmark_ce_runtime.py score OUT [--no-guard] [--prune yes|no] [--no-repair] [--tag T]
python scripts/compare_heldout.py
```

Replies were produced by subagents answering the frozen prompts. The
checker, binder, guard and pruning are deterministic.
