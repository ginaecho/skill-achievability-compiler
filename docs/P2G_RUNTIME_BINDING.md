# P2g: runtime-bound CE compaction with a guarded repair

> **Data:** the experiment data this document cites (`runs/`, `benchmark/`) is kept on the
> branch [`gc/data_train_test`](https://github.com/ginaecho/skill-achievability-compiler/tree/gc/data_train_test),
> not on `main`. Check out that branch to reproduce the numbers or run the experiment scripts.

P2g is the recommended way to decide whether a real skill is ACHIEVABLE or
IMPOSSIBLE in a given runtime. The model writes the skill as
[Controlled English](CONTROLLED_ENGLISH.md). The binding to the runtime is
deterministic, and so is the check.

## Method

1. **Runtime manifest.** `src/skillc/data/runtimes/developer-sandbox.json`
   lists what the runtime offers:
   - tools: bash, read, write, edit, web_fetch, browser, ask_user;
   - granted resources;
   - forbidden effects: `writes_external` and `publishes`.
2. **Compaction (the LLM step).** The model writes CE in which every Tool
   declares:
   - `via`: the runtime tool that performs it;
   - `needs`: any resource from outside the runtime.

   Thinking steps are not Tools. Optional work goes on a skippable branch.
   If the reply does not parse, the model gets one retry with the located
   error.
3. **Binding (deterministic, `frontend/runtime.py`).** For each Tool:
   - if its `via` is absent from the manifest, the Tool is withdrawn;
   - if its `needs` is not granted, the Tool is blocked by a guard that
     never holds.
4. **Check.** The Z3 checker runs on the bound pack and gives
   ACHIEVABLE, IMPOSSIBLE or UNKNOWN.
5. **Repair (P2).** An IMPOSSIBLE verdict triggers one repair, guided by the
   counterexample. The model sees the refutation and may fix a compaction
   error. It may not add abilities the runtime lacks.
6. **Guard (the "g", deterministic).** A repair is rejected if:
   - it changes the Goal or the Live goal; or
   - a Tool that is kept loses a `needs`, a `runs` or an `effect`.

   If the repair is rejected, the refuted pack stands.

- **Harness:** `scripts/benchmark_ce_runtime.py`, run with
  `--method ce_rt` and the default scoring.
- **Ground truth:** every skill in a test set was executed blindly by an
  agent in the same sandbox.
- **Labels (L2):**
  - *achieved*: the executor achieved the skill;
  - *impossible*: the executor's blocker was a missing runtime tool, a
    required account or credential, or a safety-forbidden effect;
  - *inconclusive*: anything else, left out of the decided metrics.

## Results on three independent test sets

P2g was frozen before any of these sets was drawn.

| set | skills | recall of impossibles | false rejections | decided accuracy | original JSON compaction |
|---|---|---|---|---|---|
| held-out (`runs/20260926_heldout_*`) | 40 | 8/14 | 1/22 | 29/36 | 24/36 (recall 3/14) |
| fresh (`runs/20260926_tpl/`) | 40 | 12/14 | 2/24 | 34/38 | 24/38 (recall 4/14) |
| ext (`runs/20260927_ext/`) | 120 | 33/35 | 10/80 | 103/115 | not run |
| **pooled** | 200 | **53/63** (Wilson 95%: 0.73–0.91) | **13/126** | **166/189** (0.82–0.92) | — |

- **Against JSON.** On the two sets where the original JSON compaction also
  ran:
  - decided accuracy: P2g 63/74, JSON 48/74;
  - recall: P2g 20/28, JSON 7/28;
  - paired comparison: 18 skills better, 3 worse, exact McNemar p = 0.0015.
- **Extension corpus.** On the ext set, P2g scores 49/54 on the decided skills
  of the extension corpus (`benchmark/ce_sources_ext`), which includes 3
  repositories new to the project.
- **Labelled scenarios.** 16/16 impossible scenarios were refuted, with no
  false refutations.
- **Pooling.** Combining the three sets is a post-hoc choice. On each set on its
  own, P2g is the best of the methods run on that set.

## What P2g still gets wrong

- **Main remaining error: optional external steps.** The biggest source of
  error is whether an external step (publish, deploy, submit) counts as part
  of the core deliverable. Here the executor and the compactor can
  legitimately disagree.
- **ext set: 10 false rejections.** Six of them are skills where the executor
  verified the local part and treated publishing as optional; examples are
  pr-writer and make-repo-contribution.
- **Misses.** They occur when the compactor makes a real requirement
  optional.
- **Two variants that did not help:**
  - two goal levels with branch pruning ("P3"): 0 false rejections, but
    recall fell to 6/14;
  - adding library hints to the prompt ("TPL", see
    [LIBRARY_TEST.md](LIBRARY_TEST.md)).
