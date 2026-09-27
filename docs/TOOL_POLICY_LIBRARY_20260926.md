# Tool-policy library (TPL) v0: pre-registered test on 40 fresh skills

Follow-up: the library v1 as a deterministic veto on top of P2g, tested on
120 new skills, is in
[`LIBRARY_VETO_EXT_20260927.md`](LIBRARY_VETO_EXT_20260927.md).

Plan and criteria: `runs/20260926_tpl/PLAN.md`, committed with the frozen
library before any fresh prompt was answered. Data: `runs/20260926_tpl/`
(`comparison.json`, `execution/`, one directory per method).

## Result

**TPL v0 fails two of its three pre-registered criteria.** On the same 40
fresh skills, the plain runtime-bound method with guarded repair (P2g) was
better. The library's contribution was net negative.

Fresh set, L2 labels (24 achieved, 14 confirmed impossible, 2
inconclusive):

| method | IMPOSSIBLE | precision | recall | false rejections | decided accuracy | vs json (better/worse, p) |
|---|---|---|---|---|---|---|
| json (original) | 8 | 4/8 | 4/14 | 4/24 | 24/38 | — |
| P1 | 22 | 13/21 | 13/14 | 8/24 | 29/38 | 10/5, 0.30 |
| **P2g** | 15 | **12/14** | **12/14** | **2/24** | **34/38** | **11/1, 0.006** |
| TPL, no repair | 15 | 10/15 | 10/14 | 5/24 | 29/38 | 8/3, 0.23 |
| TPL, binder without library | 13 | 10/13 | 10/14 | 3/24 | 31/38 | 9/2, 0.07 |
| TPL, no pruning | 25 | 13/23 | 13/14 | 10/24 | 27/38 | 10/7, 0.63 |
| **TPL** | 13 | 10/13 | 10/14 | 3/24 | 31/38 | 9/2, 0.07 |

The table shows L2 metrics only. Precision uses decided rejections, so rejections of inconclusive skills are left out.

**Criteria:**

1. **Recall at least 20 points above P2g's, and at least 0.75.** TPL
   10/14 vs P2g 12/14. **Not met.**
2. **False rejections no more than P2g's.** 3 vs 2. **Not met.**
3. **Labelled scenarios 16/16 with 0 false refutations.** **Met.**

## Why TPL lost (case level)

- **The escape hatch was used on real requirements.** The TPL prompt told
  the model to put optional work on a skippable branch and listed "known
  local alternatives". Pruning then removed those branches. Three true
  impossibles were lost this way:
  - **expo-brownfield** needs a native iOS/Android build. The
    `mobile_device` entry said "type-checking or a web preview is usually
    accepted", so the model made the device step optional.
  - **hf-mcp**: the Hugging Face MCP tools were made optional.
  - **expo-migrate-module**: its Swift build verification was pruned.

  Without pruning, TPL catches 13/14, but it falsely rejects 10/24. The
  library shifts the model's decisions on the same knob in both
  directions; it does not add information the knob can use.
- **An obligation became a mandatory step, causing a false rejection.**
  dimensional-analysis matched `agent_spawn` ("subagents"). The model made
  the spawn mandatory; the executor did the work itself.
- **The binder half of the library had no effect on this set.** "Binder
  without library" gives verdicts identical to TPL. No fresh skill
  exercised a program the library marks unavailable. The effect-policy and
  `agent_spawn` bindings changed no final verdict that pruning did not
  already decide.
- **Coverage worked but did not help.** Every TPL reply covered all of its
  obligations on the first attempt (0 retries), so the model did account
  for every requirement. Recall was lost where it decided those
  requirements were optional.

The lesson: forcing a requirement to be mentioned does not stop the model
from placing it where it does not count. The deciding judgement, whether a
requirement is part of the core deliverable, stays with the LLM. The
library's substitute hints pushed that judgement toward "optional" at
exactly the wrong moments.

## Secondary: pooled evidence for P2g (two independent held-out sets)

P2g and json were both fully defined before either held-out set was drawn.
Pooling the two sets is a post-hoc choice, so it is reported as secondary.

| | decided accuracy | recall (L2) | false rejections |
|---|---|---|---|
| json | 48/74 | 7/28 | 5/46 |
| P2g | **63/74** | **20/28** (Wilson 95% 0.53–0.85) | **3/46** |

Paired: 18 skills better, 3 worse, exact McNemar p = 0.0015.

This is the first statistically significant result in the series. Binding
the compaction to a runtime manifest, plus one guarded, counterexample-
guided repair, clearly improves IMPOSSIBLE accuracy over the original
method on fresh skills. The per-set variation (P2g 29/36 on held-out,
34/38 on fresh) is within what n ≈ 40 allows.

## What this means for the library idea

The accumulated-knowledge idea is not refuted by this run; v0 as designed
is. What the data supports:

1. **Keep the library as evidence, not as prompt hints.** Remove the
   substitute text from the prompt. Substitutes invited the model to
   downgrade real requirements.
2. **Obligations must bind, not just be mentioned.** When a matched
   requirement comes from the skill's core description (frontmatter, main
   workflow) rather than an aside, the binder should refuse to let it sit
   on a skippable branch. That judgement then becomes a deterministic rule
   on the text position, rather than an LLM choice.
3. **Keep the entries that were right.** Notion, Linear and Sentry MCP;
   Azure, AWS, Expo and Hugging Face accounts; `writes_external`. On this
   set they matched true impossibles and cost no false rejections. The
   problem was the escape hatch, not the knowledge.

A v1 along these lines needs its own plan and a new fresh set. About 64 of
the 294 collected skills are still unused.

## Incidents

- Executors wrote no files outside their work directories, and none used a
  connector. The strengthened executor prompt held on this run; for
  example, all three Notion skills stopped at the connector boundary.
- Executor dependency caches filled the disk twice. The caches were
  cleared; no result files were affected.
- One executor was accidentally not launched at first (imagegen). It was
  launched late with the same prompt.
