# Lemma 3: why it is needed, what it does, and what is still open

Lemma 3 in the paper (`skillachievability.tex`, `\label{lem:inst}`) is
*"The symbolic abstraction satisfies the hypotheses"*. This note explains it
in plain terms. It was checked against the paper and the checker's code
(`src/skillc/checker.py`) as of 4 October 2026.

## 1. Before Lemma 3: what was the problem?

The checker cannot run the real world. It explores a *simplified* (abstract)
version of it. Theorem 1 (refutation soundness) says:

> If the simplified search finds no way to reach the goal, then no real run
> reaches the goal, **provided** two rules hold.

The two rules are written `step-sim` and `goal-sim` in the paper, over the
abstraction `abs`:

- **step-sim**: every real step can be copied by a step in the simplified
  search.
- **goal-sim**: whenever a real state meets the goal, its simplified copy
  meets the goal too.

Together they mean the simplified search never *loses* a real behaviour.
Theorem 1 is proved in Coq, but as a **template**: it takes the two rules as
assumptions. Its proof is "if a real run reached the goal, copy it step by
step; the copy also reaches the goal; contradiction."

**The gap.** Theorem 1 is true for *any* simplification that obeys the rules.
Nothing showed that *skillc's* simplification obeys them, so formally the
headline guarantee ("an IMPOSSIBLE verdict is never wrong") was never attached
to the tool. `theory-fixes-explanation.md` calls this "the missing bridge".

This is not a technicality. Here is a simplification that breaks the rules.
A skill has `budget = 5`, and an action `spend` inside a loop: it needs
`budget >= 3` and sets `budget := budget - 3`. The goal is `budget < 0`.
Suppose the simplified search forgot numeric updates inside loops and kept
"budget = 5" forever. It would never see `budget < 0` and would answer
IMPOSSIBLE, even when a real run, from another starting value or with a
non-deterministic effect, does reach the goal. Theorem 1 would still be
"true", but its assumption would be false, so the answer would be wrong.
Something has to rule this out for the real design.

## 2. What Lemma 3 does

Lemma 3 describes exactly how skillc simplifies a state, and proves that the
two rules hold for it.

- **Facts are exact.** The true/false facts (e.g. `file_uploaded`) are kept
  exactly. In the code: `State.true_preds`.
- **Numbers are a constraint.** The numbers are not kept exactly. Instead the
  checker keeps a constraint ψ that they are known to satisfy, e.g.
  `budget0 >= 0 and budget1 = budget0 - 3`. In the code: `State.arith`.
- **After an action** the facts get the same add/delete update as in reality.
  The constraint is replaced by the **strongest postcondition**: the most
  precise statement of what is true after the effect, given what was true
  before.
- **Widening.** At a loop's back edge the checker may throw the constraint
  away (ψ becomes "anything", ⊤). This guarantees that the search terminates.
  In the code: `_widen`.

The proof is short:

- **goal-sim**: the real numbers N satisfy ψ. So if the real state meets the
  goal, N itself shows that "ψ and goal" is satisfiable, which is the
  checker's goal test.
- **step-sim**: if the real action can fire, its guard is true of N, so
  "ψ and guard" is satisfiable and the checker also takes that step. The facts
  update identically, and the real successor satisfies the strongest
  postcondition by definition.
- **Widening**: "anything" is satisfied by every number, so dropping ψ only
  *adds* possibilities. That can make the checker less precise, but it never
  makes an IMPOSSIBLE answer wrong (Theorem 2).

So Lemma 3 connects Theorem 1 to the tool: an IMPOSSIBLE from skillc's
actual search is sound.

## 3. The problems with Lemma 3

**a) As first written, it did not fit Theorem 1 (fixed 30 Sep 2026,
commit `6505cbf2`).** Theorem 1 originally required the simplification to be
a *function*: one simplified state per real state. But skillc's constraint
depends on *which path* the search took, so one real state can have many
simplified copies. The fix:

- generalised Theorem 1 to a *relation* (`refutation_sound_rel`);
- proved the old functional form as a special case
  (`refutation_sound_fun_is_rel`);
- mechanized Lemma 3 in Coq (`SymbolicInstance.symbolic_refutation_sound`).

**b) It is proved for a model of the checker, not for the code.** The Coq
proof treats constraints as abstract mathematical predicates. Two points are
still argued only on paper, as the paper's limitations section says:

- that the code's z3 formulas mean those predicates. The code renames each
  variable per step (`budget__1`, `budget__2`, ...) rather than computing the
  postcondition directly;
- that the z3 solver answers correctly. Where z3 gives up ("unknown"), the
  code counts the query as "possible", which is the safe direction.

**c) The checker does things the lemma does not cover.** Reading
`checker.py`, three behaviours sit outside Lemma 3 and need their own
argument.

- **Pruning revisited loops.** When the search returns to the same loop with
  the same true/false facts, it stops (`loop_seen`, keyed on the loop name and
  the facts). After widening this should be the same state as one already
  explored, so it is likely fine. But it is neither proved nor mechanized, and
  it relies on loop names being unique.
- **Other refusal kinds.** Some IMPOSSIBLE-type verdicts come from separate
  checks: the whole-session typing pass (`NON_CONFORMANT`) and the adversarial
  mode, where the environment picks branches. Lemma 3 and Theorem 1 cover only
  plain reachability, so those verdicts rest on other theorems.
- **Goal checkpoints.** A goal marker that fails ends that path. This matches
  the paper's goal rule, but it is part of the search design, not of Lemma 3.

**d) A wording leftover in the paper.** After the switch to a relation,
Theorem 1's statement and proof still use function notation: "from
abs(G, W0)" and "abs(C0) ->* abs(C)". The definitions just above it use the
relation abs(C, A). The Coq version is correct; only the text is
inconsistent, and it is a small fix.

## In one sentence

Before Lemma 3, the paper proved "IMPOSSIBLE is never wrong *for any
well-behaved checker*" without showing that skillc's checker is
well-behaved. Lemma 3 shows it, mechanized for a model of the checker. Still
open:

- tie that model to the actual z3 encoding;
- cover the loop pruning;
- fix the function notation in Theorem 1's text.

## Where it came from

- 1 Jul 2026, `36ad52ec`: Theorem 1 with its two hypotheses.
- 28 Aug 2026, `ea975889`: the professor's red-marked revisions, which do not
  touch this part.
- 29 Aug 2026, `8d898b8f`: Lemma 3 first written, among the blue-marked
  theory fixes. Explained the same day in `theory-fixes-explanation.md`
  (`c4294528`).
- 30 Sep 2026, `6505cbf2`: Lemma 3 mechanized in Coq and restated.
