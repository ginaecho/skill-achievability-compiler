# The paper

`skillachievability.tex` — *Can This Agent Even Do That? A Decidable
Goal-Achievability Type Discipline for LLM-Synthesized Agent Skills*,
with `skillachievability.pdf` built from it.

The source uses the supplied NeurIPS 2026 double-blind workshop template
(`neurips_2026.sty`) for *Who Verifies the Agents? Toward Reliable Agent
Development*. The main text is six pages, followed by references, a technical
appendix containing the full verified formal development, and the required
NeurIPS checklist (`skillachievability_checklist.tex`). The formatting archive
and its unmodified example/checklist sources are retained alongside the paper.

## Source of truth for the core rules

`tas.tex` is the **authoritative statement of the core formal rules** —
the global-type grammar, the `prt`/`cap` definitions, the typing rules
(`T-Comm`/`T-Act`/`T-Goal`/`T-End`), the session and global labelled
transition systems (`S-*`, `G-*-E`, `G-*-I`), and the Subject Reduction /
Session Fidelity statements. It is maintained by the professor and edited
directly; treat it as the canonical version of any rule it contains.

`skillachievability.tex` is the **full paper**, which embeds those rules
inside the surrounding prose, proofs, figures, and Coq listings.

**Integration workflow:** when `tas.tex` is updated, diff it against the
committed copy, then port each changed rule/definition into
`skillachievability.tex` — keeping the paper's presentation conventions
(clean `\inferrule`/`mathpar`, subscript transition labels) and fixing any
obvious source typos. Any point where a rule cannot be transcribed verbatim
without breaking the surrounding proofs (e.g. a world-pairing or side-condition
question) is flagged inline with a `% NOTE (integration)` comment and raised
with the professor rather than silently changed. `tas.tex` wins on the rules;
the paper wins on prose and proofs.

This revision replaces the projection-based conformance system of the earlier
extended draft (local types, projection with merge, a separate Gay–Hole
subtyping relation) with a **direct typing discipline**: `T-Comm`/`T-Act`/
`T-Goal` type a whole session configuration against the global protocol in one
coinductive judgment, with no local-type grammar, no projection function, and
no merge operator. The receiver-side safe slack and the unobserved-choice
(deadlock) check are structural side conditions of a single rule (`T-Comm`),
rather than a separate relation and a separate realizability check; sender
labels are exact. This direct style follows the synthetic MPST
line; the paper's contribution is the guarded world and goal-achievability
layer. The existential reachability machinery that decides achievability over
the pack (`Γ;G ⊨ ◇φ_goal`, Appendices B--C) still needs no session
`𝕄` at all — it is what lets the checker run before any skill is declared.
This revision makes goal markers blocking checkpoints in the head-only
achievability reduction.

**New in this revision:**
- Appendix C.2 (`T-Comm`/`T-Act`/`T-Goal`) replaces the old local-type process
  typing, projection/realizability, and separate subtyping sections.
- Operational correspondence (Appendix D.3): **Subject Reduction** (`thm:sr`) and
  **  Session Fidelity** (`thm:sf`) for the direct judgment over a *labelled*
  transition system (Appendix B carries transition labels `Λ`, a participant map
  `prt`, and a global
  LTS split into head `-E` rules and interleaving `-I` rules), with the full
  inductive proofs written out. **Both are mechanized axiom-free with full
  bystander interleaving** for the single-label communication fragment in
  `../proof/DirectTypingSR.v` (`subject_reduction`, `session_fidelity`) for its
  single-label communication model. Observable goal labels and the paper's
  participant-matching side conditions are not yet represented in that Coq
  model. The
  world-changing *action* interleaving needs an effect-commutativity side
  condition (participant-disjointness alone does not imply effects commute over a
  shared world) and is proved on paper; the head-move action case is mechanized
  in `DirectTyping.v`. Goal markers are now **observable labels**: `S-Goal`
  (session) and `G-Goal-E` (global, head) emit `✓φ`, and `G-Goal-I` commutes a
  continuation step under a still-pending marker. The world-changing case of
  `G-Goal-I` (a firing that can falsify a pending `φ`) is handled conditionally
  by the paper's goal-stability hypothesis; removing that hypothesis is left to
  the limitations and future-work section. Per the professor, `G-Goal-I`
  remains general and each session carries a
  set of goals over which `S-Goal` ranges.
- `proof/DirectTyping.v`: the new Coq development — `type_directed_safety` /
  `progress`, and `HandoffInstance`, mechanizing the paper's own planner/worker
  example on both sides (the good handoff is typed and reaches the goal; the
  bad handoff — both roles start with an input — is proved `Stuck`, hence
  untypeable by any non-trivial protocol).
- A corrected `T-Act` world/type pairing (lockstep with `World-Act`/`G-Act`) and
  a `T-Comm` that keeps receiver-side `Sub-Ext`; sender labels are exact.
- The implementation section now states plainly that the reference
  implementation's conformance check (`session.py`: projection, merge, then
  direct conformance) is an *algorithmic* adapter for the *declarative*
  judgment of Appendix C.2 — asserted
  equivalent, not (yet) mechanized.
- The adapter now also discharges the `prt` side conditions of
  `T-Comm`/`T-Act`/`T-Goal`. `session.participants` transcribes `prt(G)` from
  `tas.tex`; a declared role outside `prt(G)` is refuted (its contract is
  `End`), and a participant the pack declares nothing for is *reported* on the
  verdict (`assumed_conformant`) rather than silently assumed — the
  Participant-agreement lemma (`prt(G) = prt(M)`) is a premise of the judgment,
  but an undeclared role offers no behaviour to refute.
- **Appendix E (token economics)** quantifies the broader-impact claim that
  pre-execution refutation reduces wasted computation. The trusted path spends
  zero tokens; compaction is linear and paid once per skill version; the run it
  avoids is quadratic in turns and recurs per invocation. The model, its
  conservative defaults and their justification live in
  `../src/skillc/tokens.py` and `../docs/TOKEN_ECONOMICS.md`, and reproduce
  with `skillc cost`. The runtime side is explicitly a model, reported as a
  band — it prices a run that, if the refutation is right, never happens.

This intentionally supersedes an earlier, more extended draft (establisher
closure, `Proj-Obs`, adversarial achievability, the 32-bundle real-skill study)
in favor of this direct-typing core; that material remains in git history and
is not part of this revision's claims.

The 2025--2026 related-work entries were verified against primary sources in
`../docs/PILLAR3_PRIMARY_SOURCE_REVIEW.md`.

## Build

```bash
cd paper
pdflatex skillachievability.tex
pdflatex skillachievability.tex
```

Requires a TeX Live with `mathpartir` (`texlive-science`) and the usual
AMS/TikZ packages (`texlive-latex-extra`, `texlive-pictures`,
`texlive-fonts-extra`). The NeurIPS style file is vendored in this directory.

## Relation to the Coq development

Three developments under `../proof/`, all axiom-free under Coq 8.18 (`Print
Assumptions`):

- `SkillAchievability.v` — the reachability soundness core: refutation
  soundness (T1), tolerance soundness (T2), capability monotonicity (T3), and
  the `FlightInstance` concrete instance (main-text overview and Appendix D).
- `DirectTyping.v` — the direct-typing safety core: `type_directed_safety` /
  `progress` (Appendix D.3), and `HandoffInstance`, the mechanized
  planner/worker example.
- `DirectTypingSR.v` — subject reduction and session fidelity for the
  single-label communication model with full bystander interleaving.

These are theorem checkers for the explicitly identified paper fragments, not the
compiler. The compiler is the `skillc` Python package in this repository.
Decidability (`thm:dec`) and undecidability under dynamic spawning
(`thm:undec`) are
proved on paper, not mechanized; mechanizing the decision procedure itself, the
declarative/algorithmic conformance equivalence, and recursive ($\mu X.G$)
protocols are future work (Section 7 and Appendix D).
