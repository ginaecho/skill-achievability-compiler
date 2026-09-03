# ECOOP review — R13 (do the theorems say what Coq proved?)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member. R12 closed seven findings, all cosmetic, provenance or hygiene. This
round attacks the one thing no round has done exhaustively and the one that would sink the paper
if it were wrong: **does each theorem in the text state what Coq actually proved?** `STATEMENTS.md`
exists precisely so a referee can check that without opening the sources, so I used it as a referee
would.

**Version reviewed.** `main.tex` md5 `e54513ff…`, 28 pages, body ending 25, References opening 26,
0 errors, 0 overfull boxes.

## Method

For each load-bearing citation I read the elaborated Coq statement beside the sentence that cites
it, and asked whether the sentence over-claims: a missing hypothesis, a strengthened conclusion, a
quantifier moved. Twenty-four results, chosen as the ones the argument rests on rather than at
random: `bridge_run`, `bridge_every_configuration`, `hrun_split`, `budget_distributes`,
`markers_are_met`, `marker_reached_is_not_futile`, `every_label_steps`, `canon_conforms`,
`two_role_bridge_nonvacuous`, `Gmiss_safe`, `Gmiss_uninhabited`, `TC_exact`, `TC_regular`,
`TC_seq_interface`, `TR_exact`, `TC_is_TR`, `cands_closed`, `decide_mu_correct`,
`principal_characterises`, `tolerance_antitone_in_ctx`, `severity_monotone_in_budget`,
`tolerance_degree_is_a_threshold`, `severity_exhaustive`, `reach_mu_iff_run`,
`robust_benign`, `assured_downward`, `benign_is_not_robust`, `interface_projection`,
`strips_cap_cone`, `safeT_congruence`, `repair_guard_exact_ab`, `repair_reorder_sound`,
`repair_compensate_sound`, `guard_abort_is_futile`, `global_abort_is_idempotent`,
`narrowing_asymmetry`, `contractiveness_is_necessary`.

## Findings

**F1 — C2 excluded $\kstar$ from its own principality claim.** "the tolerated budgets being
exactly those *below* it" reads as strictly below; `principal_characterises` says
`safeT b <-> b <= k`, and Theorem 11 itself says `$\le\kstar$`. The summary contradicted the
theorem it summarised. Fixed to `$\le\kstar$`.

**F2 — Theorem 34 omitted a hypothesis its Coq statement carries.** `guard_abort_is_futile`
requires `~ Phi (ab W)` — the goal does not hold at the abort world. Without it the conclusion is
not \Fut{} but \Ben{}, so the omission is not decorative; the narrative simply did not mention it.
The theorem now states it, paid for by tightening two sentences in the same paragraph so the body
still ends on page 25.

**Nothing else.** The other thirty-five statements say what the paper says they say, hypotheses
included — among them the ones most tempting to overstate: `budget_distributes` really is about
runs and really does require the acting roles to be covered; `interface_projection` really is
restricted to `uses U G`, the residual's own tools, as the text insists; `canon_conforms` really
needs `two_role` and a runtime where every call has an answer, both of which the text lists;
`decide_mu_correct` really needs the world set closed under the transition relation, which is the
"finite abstract world" the text assumes; `severity_exhaustive` really is conditional on the two
decidability disjunctions, which Assumption 3 states and does not hide.

## Also checked this round

- **Bibliography.** 61 entries, no duplicates, every one cited, no citation missing an entry.
- **Cross-references.** All 36 `Theorem~\ref` sites resolve to a theorem whose title matches the
  claim made at that site. No stale pointer survives the section renumbering.
- **Support.** Every theorem, lemma, corollary and proposition in the paper carries either a
  `\coqok` citation or a paper proof. None is asserted bare.

## Verdict

**Score: A (accept), confidence 5/5.** Two findings, both in the paper's description of its own
proofs, both fixed. The mechanization itself is unchanged and needed no change: what was wrong was
a summary that contradicted its theorem and a narrative that dropped a hypothesis. The
correspondence between the paper and the development is now checked result by result for everything
the argument rests on, and `STATEMENTS.md` is regenerated so the next reader can repeat it.
