# ECOOP review — R14 (does the artifact back what the paper promises?)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member. R13 checked the paper's theorems against Coq and found two. This round
turns the check around: **the development proves 189 results and the paper cites 141 of them — is
anything the paper claims sitting in the artifact uncited?** Plus the mechanical hygiene no round
had run: admits, axioms, notation defined before use, duplicated prose.

**Version reviewed.** `main.tex` md5 `189c3f8e…`, 28 pages, body ending 25, References opening 26,
0 errors, 0 overfull boxes, 144 citations after this round's additions.

## Findings

**F1 — the intro's vacuity claim pointed at nothing.** "the cone-of-influence and congruence
theorems are instantiated where their hypotheses could have been satisfiable nowhere" is exactly
the claim a referee checks after reading that the predecessor died of vacuity. The instantiations
exist — `cone_is_not_degenerate` exhibits two *distinct* worlds of one cone class, so the
transport is not between a world and itself; `congruence_is_not_degenerate` exhibits a context
that is not the hole, with both plugs safe — and both are audited, and **neither was cited**. A
referee had no way to follow the claim to the proof. Also uncited: `Ggood_is_robust`, which shows
\Rob{} is inhabited, the one thing missing from the strictly-stronger argument, which until now
exhibited only a \Ben{} residual that is not \Rob{}. All three are cited now.

**F2 — $\kstar$ was used 80 lines before it was defined.** C2 talks about $\kstar$ being
principal; the tolerance degree is not named until \S2. Glossed at first use.

## Checked clean

- **Coq hygiene.** No `Admitted`, no `admit`, no `Axiom` anywhere in the development. The
  `Variable`/`Hypothesis` occurrences are section binders, discharged into the exported
  statements — which is what `STATEMENTS.md` shows and what `Print Assumptions` confirms.
- **The other 44 uncited results** are internal lemmas, the running example's supporting facts, and
  the predecessor audit's own theorems. Two look like headline material and are not:
  `catastrophe_implies_untypable` and `untypable_implies_catastrophe` are the two halves of
  `TC_exact` restated in severity vocabulary, and Theorem 10 already states it.
- **Notation.** Every other notation the paper introduces (`safeT`, budgeted hazard and goal
  reachability, \Rob) is defined at or before first use.
- **Prose.** 409 sentences, one near-duplicate pair: the abstract's opening and the introduction's,
  which is what an abstract is for.
- **Environment.** Coq 8.18.0 and OCaml 4.14.1, exactly as `\supplement` and the README state.

## Page budget

The three citations cost more lines than they look, and the conclusion spilled to page 26. Paid for
by compressing four paragraphs — \S7's projection aside, \S12's TRAC and dead-ends paragraphs, and
\S13's scope list — without dropping a disclosure or a monitor kind: every hedge the limitations
carried is still there, reworded. Body ends on 25.

## Verdict

**Score: A (accept), confidence 5/5.** Two findings, both fixed. F1 is the one that mattered: a
paper whose predecessor was withdrawn for vacuity cannot make an unsourced claim that its own
theorems are non-vacuous, and it no longer does.
