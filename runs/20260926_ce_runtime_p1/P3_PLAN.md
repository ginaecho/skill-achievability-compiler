# P3 plan: two goal levels + runtime branch pruning (pre-registered)

Written and committed before any P3 prompt was answered and before any
held-out skill was compacted or executed.

## Why (from P1/P2 on dev + control)

P2g (runtime-bound CE, one counterexample-guided repair, deterministic repair
guard) left 16 false rejections on executor-achieved skills (9 dev, 7
control). 13 of them share one shape: the skill describes a local core
deliverable (write the provider and run its tests, build the widget, scaffold
the agent) and then an account-bound live step (deploy, publish, run against
a live cloud). The compactor put the live step on the mandatory path to the
Goal; the executor delivered the core artifact. The verdict depends on the
elided goal G, and the compactor has to state it explicitly.

A second, deterministic cause: the whole-session typing judgment (T-Comm)
quantifies over every branch of a choice, so a skippable branch containing a
runtime-blocked Tool refutes the protocol as NON_CONFORMANT even though the
agent never needs to take that branch. Making live work "skippable" (P2's
repair (b)) therefore could not work for blocked steps.

## Method P3 (`--method ce_lv`)

1. Prompt: P1's prompt with rule 10 replaced by "Two goal levels" (`Goal:` =
   core deliverable; optional `Live goal:` = the effect outside the runtime;
   steps that only serve it go in an observed choice with a `skip` branch; a
   decision test for when the live effect IS the Goal). CE gains the optional
   `Live goal: F.` statement (grammar, renderer and round trip tested).
2. Binder (deterministic): branches of the agent's own non-external choices
   that invoke a withdrawn or blocked Tool are pruned when a runnable branch
   remains. External choices are never pruned.
3. One located-error retry (as P1), then one counterexample-guided repair
   with the deterministic guard: Goal and Live goal unchanged, and every
   surviving Tool keeps its `needs`.
4. Primary verdict: the core Goal, protocol scope. The live verdict
   (Goal and Live goal) is reported, not scored against executor labels.

## Evaluation A (development; not independent)

The same dev (47), control (50) and labelled (32) sets and labels as P1/P2.
It is not independent: P3 was designed after inspecting these cases.

## Evaluation B (confirmatory, held-out)

- Cases: the next 40 skills in the A/B's own stratified order
  (`select_real`), skipping the 150 A/B skills. None was compacted, executed
  or inspected before this plan was committed.
- Methods on the same 40: `json` (the original JSON compaction with its
  retry), `ce_rt` P1 then P2g (repair and guard, no pruning, as defined
  before P3), and `ce_lv` P3. Subagents answer frozen prompts; no code.
- Ground truth: EVERY held-out skill is executed blindly with the same
  executor prompt as before, regardless of any verdict, so recall is
  measurable. Labels L1/L2 as in RUNTIME_BINDING_PLAN.md.
- Metrics per method: false rejections on executor-achieved skills (paired
  McNemar vs json and vs P2g), IMPOSSIBLE precision on decided labels
  (L1, L2, Wilson 95%), recall of L2-confirmed impossibles, and decided
  accuracy.

## P3 success criteria (held-out, primary verdict)

1. Fewer false rejections on executor-achieved skills than json.
2. L2 precision at least json's and at least P2g's.
3. Recall of L2-confirmed impossibles not lower than P2g's by more than one
   skill.
4. Evaluation A: labelled 16/16 refuted with 0 false refutations.

n = 40 is small; intervals are reported, and no claim is made beyond them.
