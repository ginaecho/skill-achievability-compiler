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
- A **harness-framed introduction**: a skill is presented as one way of writing
  down part of an agent's harness, motivated with measured multi-agent failure
  rates and specification-level interventions, and the trust-boundary figure is
  redrawn as two zones split by a single horizontal boundary that only the pack
  crosses. Six new references come with it (`harnesssurvey`, `harnessfix`,
  `agentskills`, `adas`, `aflow`, `cemri`).
- A qualification to `thm:cap`: `cap_monotone` mechanizes the transport half
  over an inclusion of step relations; reducing `Γ ⊆ Γ'` to that inclusion is
  the `World-Act` argument, on paper.
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
`../docs/PILLAR3_PRIMARY_SOURCE_REVIEW.md`. **Not yet covered by that review:**
the six entries added with the harness-framed introduction (`harnesssurvey`,
`harnessfix`, `agentskills`, `adas`, `aflow`, `cemri`) and the figures quoted
from them in Section 1 (the 41--86.7% failure range, the 15.6% task-success
improvement, the 6.3--18.4 point completion lift). Those need the same
primary-source pass before submission.

## MLADS+ Agents adaptation

`MLADS_AGENT_Submission.docx` is the canonical implementation-focused technical-talk
proposal adapted from `main_submission.pdf` and repository evidence using the
supplied December 2026 MLADS Word template.
`MLADS_AGENT_Submission.pdf` is its rendered preview. The Word document follows the
template's Introduction, Related Work, Methodology, Data, Results, and
Implications / Conclusion structure: four content pages, followed by a separate
references page (five PDF pages total). Its structure and visual balance are
informed by the five supplied proposals in `MLADS_examples`, especially their
problem-to-method-to-evidence narrative and practical takeaways. The introduction
is one paragraph covering business motivation, importance, Agents alignment,
the safety gap, the main contribution, and the confirmed first-submission status.
It preserves the source paper's goal-achievability objective while emphasizing
contract binding, deterministic preflight and planning, protocol checking, MCP
integration, and runtime verification. It reports two separate measured comparisons:
the corrected repeated-use study (22,892 tokens with SkillC versus 240,169
without, 90.47% fewer across 20 attempts on four independently impossible
tasks, with real API calls and simulated tool actions), and the 56-scenario
live-backend comparison (35,220 without SkillC versus 18,758 with deterministic
gating, 46.74% fewer, with all 28 achievable cases completed in each configuration).
The corrected study's first-use reduction is 52.34%; the 90.47% figure
amortizes compaction over five requests per unchanged skill. It also reports
the LLM-compaction overhead and the direct executor's failed payload, rather
than presenting either as an unqualified saving.

Evidence comes from `../docs/LIVE_BACKEND_BENCHMARK_20260921.md`,
`../docs/COMPACTION_PRECISION_ASSESSMENT_20260921.md`, the real-skill and semantic
validation reports, and their saved run artifacts. The 36-skill snapshot,
semantic mutation study, 15-pack corpus, and 32-contract planning replay remain
separate evidence sets. The proposal distinguishes measured provider usage from
modeled economics and states the bounded-adapter and prototype limitations.
The original manuscript and template are unchanged.

The main document contains four figures and two editable tables: a redrawn
trust-boundary graph, implemented SkillC architecture, all 14 per-family token
reductions, and proposed Microsoft Agent Framework integration, alongside the
validation signals and corrected first-use/repeated-use comparison. Results
include the full live decision matrix (positive = IMPOSSIBLE), actual completion,
the weighted savings formula, and session/tool/API/token accounting; the final
content page covers integration, formal guarantees, production status, and
actionable safety guidance. The aggregate cost/completion chart and original
15-case matrix remain in the supplement alongside the detailed failure cases.

`MLADS_supplementary.docx` is the twelve-page detailed supplement;
`MLADS_supplementary.pdf` is its rendered preview. It contains the original
paper's trust-boundary figure, an implementation module map, flight and
coordination walkthroughs, all 14 per-family benchmark rows and savings bars,
supporting-study summaries, and the explicitly modeled Appendix E cost table.
It also provides the proposed framework API mapping, failure policy, runtime
obligations, acceptance-test plan, and evidence provenance. The main paper's
formal-foundation summary is expanded in S9-S10: the formal model, refutation
soundness, tolerance, capability monotonicity, subject reduction, session
fidelity, incompleteness, and the termination/undecidability boundary. The proof
coverage table distinguishes scoped Coq results from paper-level arguments and
the unverified executable implementation. S11-S12 adds the corrected reuse chart
and case-level table, the historical measured PDF/XLSX comparison (85.28%
over eight failed runs), and the larger historical failure-only accounting
(98.68%, with estimated compaction costs explicitly separated from measurements).
It retains the excluded successful runs, superseded simulator results, and
negative August pilot rather than presenting the largest percentage as a
universal savings claim. Its nine figures and fifteen editable
tables retain detail without crowding the main proposal.

Ten external related works from the original manuscript appear in the numbered
bibliography, covering planning, session types, agentic workflow generation,
multi-agent failures, policy safety, and skill security screening. All ten are
cited in Related Work; they are not presented as evaluated baselines. Our own
results are presented as original data, with experiment paths and the pinned
historical commit retained as provenance in the supplement, not self-citations.
The latest content is consolidated into these canonical files; duplicate
`_revised` Word/PDF drafts have been removed. The supplementary document points
to the main bibliography rather than maintaining a second reference list.

Microsoft Agent Framework integration is **proposed, not implemented or
benchmarked in this repository**. The design uses official middleware,
workflow, MCP, and observability documentation, with references and API-version
caveats in `../docs/MICROSOFT_AGENT_FRAMEWORK_INTEGRATION_RESEARCH.md`.
The existing Azure OpenAI/MCP experiments are not labeled as framework tests.

Figures are retained in `figures/mlads_*.png`, with editable SVG versions of
the new architecture and case diagrams. Live chart values are aggregated from
saved trials and reconciled against provider-usage ledgers. The overall 46.74%
reduction uses summed tokens, not the mean of per-family percentages. The
direct executor's failed extraction and the single-pass sampling limitation
remain explicit. Figure 1 redraws the supplied graph with distinct trust zones,
aligned process cards, and color-coded verdicts; its editable source is
`figures/mlads_trust_boundary.svg`. The supplied image is retained separately
as an unchanged reference, not embedded as Figure 1.

The source manuscript is anonymous, so no presenter identity was invented.
Before uploading, supply presenter details as required by the submission process
and review the conference's AI-use policy, which the template mentions but does
not reproduce.

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
