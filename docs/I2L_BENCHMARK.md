# I2L: benchmarking compaction from intent to logical block

> **Data:** the experiment data this document cites (`runs/`, `benchmark/`) is kept on the
> branch [`gc/data_train_test`](https://github.com/ginaecho/skill-achievability-compiler/tree/gc/data_train_test),
> not on `main`. Check out that branch to reproduce the numbers or run the experiment scripts.

- **Plan:** [`runs/20260928_i2l/PLAN.md`](../runs/20260928_i2l/PLAN.md). It was committed in
  acc5b2e, before any new model call and before any block metric was computed.
- **Data:** `runs/20260928_i2l/`.
- **Scoring:** `python scripts/i2l.py blocks && python scripts/i2l.py score` writes
  `metrics.json`.

## Question

Compaction turns an **intent** (a natural-language skill) into a **logical block**: the pack
checked by the deterministic checker. The pack holds:
- Tools with runtime bindings;
- effects;
- the protocol;
- the Goal.

Earlier comparisons (JSON against P2g) scored only the final verdict, and they varied several
things at once:
- the language the model writes (JSON or CE);
- the rules and runtime information in the prompt;
- the procedure (retry, guarded repair).

This benchmark separates these factors. It also scores the logical block itself against
execution-grounded requirement labels, and adds the missing baseline: intent → verdict
directly, with no block at all.

## Arms (200 skill–runtime pairs: held-out 40, fresh 40, gr 120)

| arm | intent → | language | P2g's rules + runtime binder | repair | pairs |
|---|---|---|---|---|---|
| **J** | pack | JSON | no (original JSON prompt) | no | 80 |
| **JB** | pack + `via`/`needs` | JSON | yes | yes, same guard | 200 |
| **P2g** | CE → pack + bindings | CE | yes | yes | 200 |
| ce_gr | CE → pack + bindings | CE | P2g + software grounding | yes | 120 (gr) |
| **D** | verdict only | — | same runtime description | no | 200 |

**JB is P2g written in JSON.**
- **Same pipeline.** Everything from the parser output onwards is shared.
- **Tested equivalence.** Converting 120 existing P2g blocks to JB's JSON gives the identical
  bound pack, withdrawals and blocks (`tests/test_json_rt.py` covers this).
- **Isolation.** So P2g against JB isolates the surface language.

## Results

### Verdicts (L2 labels; decided pairs)

| arm | held-out + fresh (74) | gr (94) | all (168) | recall | false rejections |
|---|---|---|---|---|---|
| J | 48 = **0.65** | — | — | 7/28 | 5/46 |
| JB | 67 = 0.91 | 81 = 0.86 | 148 = **0.881** | 56/63 | 13/105 |
| P2g | 63 = 0.85 | 87 = 0.93 | 150 = **0.893** | 51/63 | 6/105 |
| ce_gr | — | 79 = 0.84 | — | 30/35 | 10/59 |
| D | 67 = 0.91 | 85 = 0.90 | 152 = **0.905** | 50/63 | **3/105** |

Paired exact McNemar tests (b = cases where the first arm is right and the second wrong; w = the
reverse):

| comparison | set | b / w | p |
|---|---|---|---|
| P2g vs JB (language) | all | 11 / 9 | 0.82 |
| JB vs J (rules + runtime + procedure) | held-out + fresh | 22 / 3 | **0.0002** |
| P2g vs D (block vs no block) | all | 9 / 11 | 0.82 |
| P2g vs ce_gr | gr | 9 / 1 | 0.021 (replicates `P2G_GROUNDED_TEST.md`) |

### Tokens per pair

GPT-2 BPE proxy; all rounds; prompt + reply.

| arm | total | reply (output) | calls |
|---|---|---|---|
| D | **3,471** | 26 | 1.00 |
| J (held-out + fresh) | 5,602 | 640 | 1.11 |
| P2g | 8,820 | **372** | 1.52 |
| ce_gr (gr) | 10,077 | 393 | 1.63 |
| JB | 11,364 | 1,648 | 1.72 |

### Well-formedness

| arm | valid on first reply | refuted after round 1 (→ repair) | block itself refuted with everything available* |
|---|---|---|---|
| JB | 200/200 | **144/200** | **21/200** |
| P2g | 191/200 | 95/200 | 1/200 |
| J | 71/80 | — | 9/80 |

\* The necessity fallback: the pre-binding pack is refuted even with every Tool available. This
is a structural defect, such as an unobserved choice or a goal atom nothing establishes.

JB's first replies:
- had 29 NON_CONFORMANT refutations (unobserved choices), against 11 for CE on the same pairs;
- needed a repair round for 72% of pairs, against 48% for P2g.

### Block metrics (blind judge)

**Judge reliability.**
- Each gold requirement term was aligned to the Tools of the canonically rendered block.
- An independent second judge pass covered 20% of the blocks (663 term decisions):
  agreement 0.96, **κ = 0.91**.

| arm | CR: core recall | SC: spurious core | BC: blocker captured | SW*: spurious witness |
|---|---|---|---|---|
| J (held-out + fresh) | 0.94 | 0.65 | **0.01** | 0.01 |
| JB | 0.94 | 0.54 | 0.73 | 0.25 |
| P2g | 0.91 | 0.47 | 0.67 | 0.17 |
| ce_gr (gr) | 0.88 | 0.41 | 0.70 | 0.22 |

The paired bootstrap for P2g − JB over all pairs gives:
- CR −0.024 [−0.059, 0.013];
- SC −0.067 [−0.175, 0.039];
- BC −0.055 [−0.128, 0.018].

All three intervals include 0.

**Pre-registered construct-validity check: FAILED.**
- **Prediction.** The benchmark should see the failure of ce_gr already established by
  execution (optional helpers made core), as SC(ce_gr) > SC(P2g) on gr.
- **Measured.** SC(ce_gr) − SC(P2g) = −0.006 [−0.10, 0.11].
- **Consequence.** As the plan requires, **the block-metric conclusions are withdrawn**. The
  verdict and token conclusions stand.

**Why SC missed it (exploratory).** In 5 of ce_gr's 7 new false rejections, the withdrawn
Tool does carry a gold optional term. But P2g usually keeps that term on a necessary Tool
too, just bound to a tool the runtime has (e.g. the risk scorer done `via write`).

The failure is therefore **an optional requirement on a necessary Tool that the runtime
withdrew**, not "an optional requirement on a necessary Tool". SW* measures exactly that. It
was defined after the check failed, so it is exploratory:
- the ordering is P2g 0.19 < ce_gr 0.22 < JB 0.26, in the direction of the false-rejection
  counts;
- ce_gr − P2g on gr = +0.024 [−0.064, 0.133];
- neither difference is significant.

## What this says

1. **Language (CE against JSON), everything else fixed.**
   - Verdict accuracy is statistically the same (0.893 against 0.881, p = 0.82).
   - CE's gains are **economy and well-formedness**:
     - a 4.4× shorter reply (372 against 1,648 tokens);
     - 22% fewer total tokens;
     - far fewer structurally broken blocks (1 against 21);
     - fewer repair rounds (95 against 144).
   - On gr, JB made more false rejections (10 against 3).
   - CE is the better surface language to *write* the logical block in, but not a more accurate
     one.
2. **Most of the old JSON → P2g gain was not the language.**
   - Giving the JSON prompt P2g's rules, the runtime description and the binder (JB) raises
     accuracy from 0.65 to 0.91 on the same pairs (p = 0.0002).
   - J cannot express runtime blockers at all (BC 0.01): its prompt has no runtime binding.
3. **The logical block does not buy verdict accuracy here.**
   - The direct intent → verdict baseline (D) is as accurate as P2g (0.905 against 0.893,
     p = 0.82), has the fewest false rejections (3/105) and costs 40% of the tokens.
   - The case for the logical block must rest on what D cannot give:
     - a checkable witness (which Tool, which missing runtime resource);
     - a deterministic, auditable decision that later runtime or policy changes can re-check
       without a model call;
     - a structure other tools (repair, pruning, policy) can operate on.
   - This benchmark did not measure those properties.
4. **Measuring the block itself is harder than measuring the verdict.**
   - The judge alignment is reliable (κ 0.91), and CR, SC and BC are well defined.
   - But term-level "core/optional" did not track the known compaction failure. The next
     version needs a pre-registered metric of the SW kind, tested on a fresh set.

## Caveats

- **Single model family.** One model family compacted, judged, executed and adjudicated.
- **D's prompt** included P2g's core-deliverable definition and the runtime description, so D
  is a strong direct baseline, not a naive one.
- **Blindness of J/P2g outcomes.**
  - The held-out, fresh and gr pairs were used in earlier tests, and their P2g outputs existed
    before this plan.
  - JB and D were run fresh against frozen prompts.
  - No arm was tuned after the plan.
- **Gold requirement terms** come from execution reports:
  - they cover what executors mentioned, not every requirement;
  - 25 of the 200 pairs have no gold terms and are excluded from the block metrics.
