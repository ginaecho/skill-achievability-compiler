# Prior-art audit of the severity / k-resilience paper

Second sweep, targeting the *reframed* design (the first sweep, `NOVELTY.md`,
audited the withdrawn modes/taint/grades draft). Verdicts are deliberately
harsh.

## Per-mechanism verdict

| # | Mechanism | Verdict |
|---|---|---|
| 1 | Guarded choice / misselection | **PARTIALLY SCOOPED** — closer to scooped |
| 2 | Severity: Benign / Futile / Catastrophic | **NOVEL but structurally shallow** |
| 3 | Point of no return | **SCOOPED** as a concept; novel only as a lifting |
| 4 | k-resilience / misselection budget | **PARTIALLY SCOOPED**, and the name is taken 3× |
| 5 | T-Choice-Safe (sound + complete) | Rule **NOVEL**; the *template* is 20 years old |
| — | The four repairs | **MOSTLY SCOOPED** — shrink this section |

## The single most dangerous citation

**Naik & Palsberg, _A Type System Equivalent to a Model Checker_, ESOP 2005 /
TOPLAS 30(5):29, 2008.** A syntax-directed type system proved **sound and
complete** with respect to a model checker for a reachability-flavoured
property. It scoops no mechanism, but it does three things at once: it makes
our headline theorem an *instance* of a known template; it demonstrates that
template on arguably more mainstream programs; and **it already contains the
standard rebuttal to the "so what, it's model checking" attack** (types explain
why a program is accepted, model checkers why one is rejected) — so we cannot
present that rebuttal as our insight. Cite it, position against it.

Runner-up on substance: **Aineto, Gaudenzi, Gerevini, Rovetta, Scala, Serina,
_Action-Failure Resilient Planning_, ECAI 2023** — takes the name *k-resilient*
and the bounded-possibilistic-fault structure verbatim (STRIPS setting, no
probabilities). Also **Domshlak, _Fault Tolerant Planning_, ICAPS 2013**.

Runner-up on motivation: **Pact: A Choreographic Language for Agentic
Ecosystems** (2026) — choreographies with **first-class agent choice**, mapped
to games. It owns the "choreographies where the agent may choose badly" framing.

## Naming collisions — fix before submission

Three, one of them *inside MPST*:

1. **`k-safety` already means a buffer bound in MPST** — Lange & Yoshida,
   _Verifying Asynchronous Interactions via Communicating Session Automata_,
   CAV 2019 (k-multiparty compatibility = k-safety + k-exhaustivity).
2. `k-safety` also means hyperproperties over k traces (Clarkson & Schneider).
3. `k-resilient` is taken by Aineto et al. and by distributed computing.

Rename to **k-misselection-tolerant** or **budgeted hazard-freedom**, with a
disambiguating footnote. Reviewers reward this; being told reads as sloppiness.

## Per-mechanism detail

**1. Guarded choice.** Branch predicates are Bocchi–Honda–Tuosto–Yoshida
(CONCUR 2010); assertion *violation on selection* is already the alarm
condition of the monitoring line (Bocchi–Chen–Demangeon–Honda–Yoshida
FMOODS/FORTE 2013, TCS 2017); refinements on MPST branches are OOPSLA 2020
(Zhou et al.), **ECOOP 2022** (Gheri et al.) and **ECOOP 2024** (Vassor &
Yoshida, whose "valid refined traces" is the closest published thing to our
compliant/misselecting split). Blame attribution is Jia–Gommerstadt–Pfenning
(POPL 2016). Our delta is in *use*, not mechanism: nobody asks what `¬ψ_i`
does to a world, a goal, and a hazard. Do **not** list this as a novelty.

**2. Severity.** Nothing in behavioural types classifies deviations by outcome.
Nearest: model-based safety assessment (**xSAP**, TACAS 2016; FSAP/NuSMV-SA),
where severity is *supplied by the analyst*, not computed from goal
reachability — that is the gap to state explicitly. Anticipated attack: "this
is the Cartesian product of two standard predicates presented as a taxonomy;
where is the theorem?" We need a result showing the trichotomy is not just a
product (e.g. the classes are the equivalence classes of a natural preorder on
post-deviation states, or Futile is decidable strictly more cheaply).

**3. Point of no return.** Mature planning subfield: Steinmetz & Hoffmann
(AAAI 2016, IJCAI 2017, AIJ 2017); Hoffmann–Kissmann–Torralba (ECAI 2014);
undoability/reversibility — Daum–Torralba–Hoffmann–Haslum–Weber (ICAPS 2016),
Morak–Chrpa–Faber–Fišer (KR 2020/JAIR, KR 2025). **Complexity warning:**
reversibility checking is known *harder* than planning and inherits
PSPACE-hardness unrestricted — any decidability claim must not gloss this.
Göbelbecker et al. (ICAPS 2010) detect goal unreachability *and propose model
repairs*, scooping part of mechanism 3 and part of the repair story at once.
Also Shrinah & Eder on goal-constrained safety verification of planning
domains. RL safety: Turner et al. (AIES 2020), Krakovna et al.,
Grinsztajn et al. (NeurIPS 2021).

**4. Budget.** Bounded-fault MPST already exists in parameterised form:
Barwell–Hou–Yoshida–Zhou (CONCUR 2022 / LMCS 2025) state that failure patterns
cover "a bound on the number of faulty processes"; Peters–Nestmann–Wagner
(FORTE 2022). Our honest delta: the fault is the agent's *own branch choice*
(not a crash or action failure), and the target is a **hazard** rather than the
goal — Aineto bounds failures against *goal reachability*.

**5. T-Choice-Safe.** Exact-characterization type systems: Naik & Palsberg
(above); Kobayashi & Ong (LICS 2009). Budget-indexed typing: graded modal types
(Orchard–Liepelt–Eades ICFP 2019; Marshall & Orchard 2022) and AARA session
types (Das–Hoffmann–Pfenning LICS/ICFP 2018, POPL 2023). **Anticipated attack:
"this is AARA with a degenerate cost metric."** The answer must be that the
budget is spent by an *adversarial/environmental* choice rather than by the
program's own execution — so the rule quantifies over deviations rather than
amortising — and that the exhausted-budget case is *unconstrained*, which has
no analogue in AARA (there, exhausted potential is a type error). Put this in
the paper.

**Repairs.** Guard-insertion ≈ Bocchi–Lange–Tuosto, _Three Algorithms and a
Methodology for Amending Contracts for Choreographies_ (SACS 2012) — the most
dangerous citation for this section. Compensation ≈ Carbone–Honda–Yoshida
(CONCUR 2008), Capecchi–Giachino–Yoshida (FSTTCS 2010), reversible sessions
(Mezzina & Pérez; Lanese–Mezzina–Tuosto). Branch removal ≈ Ramadge–Wonham
supervisory control and shield synthesis (Bloem et al. TACAS 2015; Alshiekh et
al. AAAI 2018; CACM 2025); choreography repair (Basu & Bultan FASE 2016;
Lanese–Montesi–Zavattaro WWV 2013; Cruz-Filipe & Montesi 2020, Coq-formalised).
Reordering ≈ saga pivot transactions; Atomix (2026) gates irreversible effects
exactly this way. **Recommendation: cut to a short applications subsection, or
keep only reordering, the one repair that uses the world-state analysis rather
than pure control-flow surgery.**

## Rebutting "it's just bounded model checking as inference rules"

Do **not** lead with "types are compositional / lightweight" — pre-rebutted by
Naik & Palsberg. Lead with, in order:

1. **Compositionality is a live, contested, currently-published axis in MPST.**
   _A Synthetic Reconstruction of Multiparty Session Types_ (PACMPL 2026) argues
   exactly this: projection-based MPST is compositional but limited; recent
   expressive techniques rely on **whole-system model checking that scales
   poorly**. Bounded reachability over protocol × world × counter is
   whole-system; T-Choice-Safe types one participant against the global type.
   **Then demonstrate it**: a case where the product model checker times out and
   the typing derivation does not. Without that experiment this is rhetoric.
2. **Completeness turns a procedure into a specification** you can write down,
   project, compose, and hand a programmer as an interface; `k` becomes a
   published contract on the endpoint, not a knob on a tool.
3. **Concede the decision procedure is routine** and claim the *modelling*.

Precedent to cite: Barwell–Hou–Yoshida–Zhou made MPST typing parametric in a
behavioural safety property validated by model checking (CONCUR 2022), and the
**ECOOP 2023** companion won a Distinguished Paper. The community has already
decided this move is publishable.

## ECOOP-specific: must engage (2022–2026)

- **ECOOP 2022** Gheri, Lanese, Sayers, Tuosto, Yoshida — Design-by-Contract
  for Flexible MPST. *(direct prior art for mechanism 1)*
- **ECOOP 2022** Lagaillardie, Neykova, Yoshida — Stay Safe Under Panic.
- **ECOOP 2023** Barwell, Hou, Yoshida, Zhou — Designing Asynchronous
  Multiparty Protocols with Crash-Stop Failures (**Distinguished Paper**).
  *The ECOOP-canonical "MPST with a fault model" paper; not citing it is
  disqualifying.*
- **ECOOP 2023** Li, Stutz, Wies, Zufferey — Async MPST Implementability is
  Decidable. *(bears on any decidability claim)*
- **ECOOP 2023** Synthetic Behavioural Typing; Dynamically Updatable MPST
  *(relevant to the repairs)*.
- **ECOOP 2024** Vassor & Yoshida — Refinements for Multiparty Protocols.
- **ECOOP 2025** Tirore, Bengtson, Carbone — Mechanised Subject Reduction.
  *Sets the bar for a mechanized MPST metatheory; expect "is your Coq
  development comparable in scope, or only the k-bounded finite fragment?"*
- **ECOOP 2026** Larsen, Scalas, Amir, Jacobs, Wagemaker, Foster — NEST.
  *Scalas co-authored "Less is More: MPST Revisited" (POPL 2019) — the person
  most likely to launch the model-checking attack and most likely to accept the
  compositionality rebuttal if we make it properly.*

**ECOOP has published nothing on LLM agents.** That is an opportunity (first at
the venue) but also a warning: the PC will be pure behavioural-types people who
discount the LLM motivation and judge mechanisms 1, 4, 5 on session-type merit
alone. **Budget page count accordingly — a long LLM motivation reads as
padding.**

## The one claim to make

> The first behavioural type theory whose fault model is the agent's **own
> selection at a protocol branch point**: misselection graded by an explicit
> budget, with typing a syntax-directed, mechanized **exact** characterization
> of hazard-freedom under at most *k* misselections. Its analytic payload is
> that pairing the protocol with a STRIPS world classifies each deviation by
> **outcome** — goal reachable, goal lost, or hazard reachable — so the system
> distinguishes failure from disaster rather than treating both as
> non-conformance.

Deliberately not claimed: that branch predicates are new (Bocchi 2010), or that
bounded-fault reasoning or dead-end detection is new (Aineto 2023; Steinmetz &
Hoffmann; Daum et al.).


---

# Third pass (after the μ-unfolding, repairs, bystander and kernel work)

New claims since the second pass, each checked against the literature:

| Claim | Nearest prior work | Verdict |
|---|---|---|
| Finiteness of the μ-unfolding closure, mechanized (`cands_closed`) | Standard for regular trees (Tirore et al. ECOOP 2025, Zooid, Castro-Perez et al.); ours is a direct substitution-based proof | supporting lemma, **not a contribution** — say so |
| Coinductive conformance typing of recursive sessions + cost-preserving simulation (`bridge_mu`) | subject reduction for MPST (Honda et al. JACM 2016; mechanised by Tirore et al.) | the *cost* (misselection budget) preserved by simulation is new; the typing is routine |
| Bystander swaps with **semantic** side conditions (commute / neutral / preserves / enables), discharged by STRIPS variable disjointness | swap/permutation of independent interactions (Honda–Yoshida–Carbone; Deniélou–Yoshida); commuting actions in planning (Chapman 1987; partial-order reduction) | the combination — a type-preservation-under-permutation theorem whose side conditions are *world-effect* independence, because the property is order-sensitive — is new in MPST; the ingredients are old |
| Verified kernel extracted from `decide_mu` and cross-checked against the tool | verified model checkers (Esparza et al. ITP 2013), CompCert-style trusted front ends | standard architecture; a credibility point, not a novelty claim |
| Live-agent non-vacuity of Catastrophic verdicts | TRAC (FAccT 2026) evaluates monitors on traces; AgentSpec/Progent evaluate enforcement | the *experiment design* (predicted severity vs. observed catastrophe, repairs with the same agent) has no precedent we found; the sample is small |

Nearest 2026 agent-side papers, re-checked: Yin, *Safety invariants for
agents orchestrating irreversible state transitions* (arXiv:2608.00783,
exactly-once execution fidelity, ledgers); Metere, *Methods for formal
verification of agent skills* (arXiv:2605.23951, capability containment);
Sun et al., *Agentic model checking* (arXiv:2605.21434, agents propose,
BMC verifies, for code). None asks which wrong choice is affordable, none
carries a budget through a bridge to sessions, none mechanizes.

**What the paper's novelty rests on, unchanged:** the question (severity of a
wrong choice, not its possibility), the budgeted semantics with its exact
syntax-directed characterization, and the bridge from protocol to session
that carries the budget. What the third pass added is *credibility*
(mechanized scope now covers recursion, repairs, bystanders; a verified
kernel; live agents), not a new headline claim.
