# The paper

`skillachievability.tex` — *Can This Agent Even Do That? A Decidable
Goal-Achievability Type Discipline for LLM-Synthesized Agent Skills*,
with `skillachievability.pdf` built from it.

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
no merge operator. Both directions of session subtyping and the
unobserved-choice (deadlock) check are structural side conditions of a single
rule (`T-Comm`), rather than a separate relation and a separate realizability
check. The existential reachability machinery that decides achievability over
the pack (`Γ;G ⊨ ◇φ_goal`, §4.2/§5.4) is unchanged and still needs no session
`𝕄` at all — it is what lets the checker run before any skill is declared.

**New in this revision:**
- §5.2 (`T-Comm`/`T-Act`/`T-Goal`) replaces §5.2's old local-type process typing,
  §4.3's projection/realizability, and §4.4's subtyping.
- Operational correspondence (§6.3): **Subject Reduction** (Thm 4) and **Session
  Fidelity** (Thm 5) for the direct judgment over a *labelled* transition system
  (§4.2 now carries transition labels `Λ`, a participant map `prt`, and a global
  LTS split into head `-E` rules and interleaving `-I` rules), with the full
  inductive proofs written out. **Both are mechanized axiom-free with full
  bystander interleaving** for the communication fragment in
  `../proof/DirectTypingSR.v` (`subject_reduction`, `session_fidelity`). The
  world-changing *action* interleaving needs an effect-commutativity side
  condition (participant-disjointness alone does not imply effects commute over a
  shared world) and is proved on paper; the head-move action case is mechanized
  in `DirectTyping.v`. Goal markers are now **observable labels**: `S-Goal`
  (session) and `G-Goal-E` (global, head) emit `✓φ`, and `G-Goal-I` commutes a
  continuation step under a still-pending marker. The world-changing case of
  `G-Goal-I` (a firing that can falsify a pending `φ`) is the open crux of the
  correspondence, left to §10; per the professor, `G-Goal-I` is intentionally
  general and each session carries a set of goals over which `S-Goal` ranges.
- `proof/DirectTyping.v`: the new Coq development — `type_directed_safety` /
  `progress`, and `HandoffInstance`, mechanizing the paper's own planner/worker
  example on both sides (the good handoff is typed and reaches the goal; the
  bad handoff — both roles start with an input — is proved `Stuck`, hence
  untypeable by any non-trivial protocol).
- A corrected `T-Act` world/type pairing (lockstep with `World-Act`/`G-Act`) and
  a generalized `T-Comm` recovering *both* `Sub-Int` and `Sub-Ext` directly.
- §7 now states plainly that the reference implementation's conformance check
  (`session.py`: projection, merge, Gay–Hole subtyping) is an *algorithmic*
  decision procedure for the *declarative* judgment of §5.2 — asserted
  equivalent, not (yet) mechanized.

This intentionally supersedes an earlier, more extended draft (establisher
closure, `Proj-Obs`, adversarial achievability, the 32-bundle real-skill study)
in favor of this direct-typing core; that material remains in git history and
is not part of this revision's claims.

Citations marked `[verify]` are placeholders flagged for bibliographic
verification and remain flagged.

## Build

```bash
pdflatex skillachievability.tex && pdflatex skillachievability.tex
```

Requires a TeX Live with `mathpartir` and `lmodern` (`texlive-science`,
`lmodern`) and the usual AMS/TikZ packages (`texlive-latex-extra`,
`texlive-pictures`, `texlive-fonts-extra`).

## Relation to the Coq development

Two files under `../proof/`, both axiom-free under Coq 8.18 (`Print
Assumptions`):

- `SkillAchievability.v` — the reachability soundness core: refutation
  soundness (T1), tolerance soundness (T2), capability monotonicity (T3), and
  the `FlightInstance` concrete instance (§2, §6.2).
- `DirectTyping.v` — the direct-typing safety core: `type_directed_safety` /
  `progress` (Theorem 4, §6.3), and `HandoffInstance`, the mechanized
  planner/worker example.

These are the theorem checkers for the paper's central claims, not the
compiler. The compiler is the `skillc` Python package in this repository.
Decidability (Theorem 5) and undecidability under autonomy (Theorem 6) are
proved on paper, not mechanized; mechanizing the decision procedure itself, the
declarative/algorithmic conformance equivalence, and recursive ($\mu X.G$)
protocols are future work (§10).
