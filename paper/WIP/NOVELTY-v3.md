# Prior-art audit v3 — adversarial pass on the seven claims

Third sweep, run against the *current* `main.tex` (severity / k-misselection-tolerance /
bridge / regular / modularity / 162-skill evaluation). `NOVELTY.md` audited the withdrawn
modes/taint/grades draft; `NOVELTY-v2.md` audited the reframed design and its third pass.
This sweep deliberately looks **outside** the session-types literature, because that is where
the damage is: the two nearest owners of the headline idea are in **reactive synthesis** and
**AI planning**, and the paper currently cites neither of the synthesis ones at all.

Search discipline: ~35 queries across DBLP, Springer, ACM DL, Dagstuhl/LIPIcs landing pages,
IOS Press, KR/ICAPS/IJCAI proceedings, lab homepages and arXiv listing snippets (arxiv.org
itself is proxy-blocked; abstracts recovered from search snippets, ACM/Springer/Semantic
Scholar pages and mirrors). Verdicts are harsh on purpose.

---

## Summary table

| # | Claim | Verdict |
|---|---|---|
| 1 | Misselection + budget *k* + tolerance degree *k\** | **NOVEL-IN-COMBINATION** (one step from INCREMENTAL) |
| 2 | Benign / Futile / Catastrophic + point of no return | **INCREMENTAL** |
| 3 | `T-Choice-Safe`, sound **and** complete | **INCREMENTAL** |
| 4 | Bridge to typed sessions; budget distribution; μ; bystanders | **NOVEL-IN-COMBINATION** — the strongest claim in the paper |
| 5 | Decidability via Node × World × {0..k}; μ-closure; extracted kernel | **INCREMENTAL** (technique **SCOOPED**, execution is credibility not contribution) |
| 6 | Modular sequential composition against an interface | **INCREMENTAL** |
| 7 | 162 skills; verdicts predict wasted / fabricated runs | **NOVEL-IN-COMBINATION**, but on a crowded and much larger-scale 2026 landscape |

---

## Claim 1 — Misselection, budget *k*, tolerance degree *k\**

**Closest prior work**

1. **R. Ehlers, U. Topcu. *Resilience to Intermittent Assumption Violations in Reactive
   Synthesis.* HSCC 2014, ACM, pp. 203–212.** Introduces **(k,b)-resilience**: synthesise a
   controller that still satisfies its specification while tolerating bursts of up to *k*
   environment-assumption violations. The construction is a product of the game graph with a
   violation counter, decremented on each assumption-violating environment move.
2. **R. Bloem, K. Chatterjee, K. Greimel, T. A. Henzinger, B. Jobstmann. *Robustness in the
   Presence of Liveness* / *Synthesizing Robust Systems.* FMCAD 2009; Acta Informatica
   51(3–4):193–220, 2014.** Defines **k-robustness**: the number of system failures is at most
   *k* times the number of environment failures; synthesis reduces to a one-pair Streett game
   in polynomial time.
3. **D. Aineto, A. Gaudenzi, A. Gerevini, A. Rovetta, E. Scala, I. Serina. *Action-Failure
   Resilient Planning.* ECAI 2023, FAIA 372, pp. 44–51** (and the follow-up **A. Rovetta et
   al., *Improving Resilient Planning Through Landmarks and Regressed State Formulas*, ECAI
   2025**). *K-resilient* plans: the agent reaches the goal as long as no more than *K*
   execution failures occur. STRIPS setting, possibilistic, no probabilities.
4. **P. Yu, S. Zhu, G. De Giacomo, M. Kwiatkowska, M. Y. Vardi. *The Trembling-Hand Problem
   for LTLf Planning.* IJCAI 2024, pp. 3630–3638.** The fault model is *literally* the paper's:
   "the agent may mistakenly instruct actions that are not intended due to faults or imprecision
   in its **action selection mechanism**". Solved over MDPs/MDPSTs, maximising goal probability.
5. **R. Meira-Góes, I. Dardik, E. Kang, S. Lafortune, S. Tripakis. *Safe Environmental Envelopes
   of Discrete Systems.* CAV 2023, LNCS 13965, pp. 349–370**, building on **C. Zhang, D. Garlan,
   E. Kang. *A Behavioral Notion of Robustness for Software Systems.* ESEC/FSE 2020, pp.
   1–12.** Robustness = the **largest set of environment deviations** under which the system
   still guarantees the property — i.e. *k\** in set-valued rather than counted currency.

**Verdict: NOVEL-IN-COMBINATION, one step from INCREMENTAL.**

What is genuinely new is the *carrier*: nobody has put a deviation budget on a **global session
type** where the deviating event is a participant's **branch selection against an asserted
guard**, and nobody reports a **tolerance degree** as the headline number of a behavioural type.
What is not new — and the paper currently does not admit — is essentially everything else about
the mechanism. Ehlers & Topcu had "tolerate up to *k* assumption violations, decided by a
product with a counter" in 2014; Bloem et al. had a *ratio*-form budget in 2009; Aineto et al.
own the possibilistic-STRIPS *K*-resilience name and structure; Zhang/Garlan/Kang and
Meira-Góes et al. own "the largest deviation set the design survives" as a computed quantity.
Yu et al. own the *misselection fault model itself*, in planning, two years earlier, and they
even name it after Selten's trembling hand. The paper's footnote in Def. 4.4 disclaims
*k-safety* and *k-resilient*, but disclaiming a name is not positioning against a construction:
a reviewer who knows HSCC/CAV will read `T-Choice-Safe` + Thm. 7.1 as Ehlers–Topcu recast as
inference rules. The honest delta to state in the paper is (i) the deviation is *internal to
the typed participant* rather than an environment/assumption event, (ii) the target is a
**hazard**, not the goal, and (iii) the budget survives a subject-reduction argument to programs
(Claim 4), which no synthesis or planning paper does because they have no type system.

---

## Claim 2 — Benign / Futile / Catastrophic, and the point of no return

**Closest prior work**

1. **V. Krakovna, L. Orseau, R. Ngo, M. Martic, S. Legg. *Penalizing Side Effects using Stepwise
   Relative Reachability.* AI Safety Workshop / IJCAI 2018 (CEUR Vol. 2419); journal version
   *Avoiding Side Effects By Considering Future Tasks*, NeurIPS 2020.** A state is scored by
   **the reduction in reachability of other states** relative to a baseline; irreversible
   actions are exactly those that collapse reachability. Benign-vs-Futile is a two-valued
   coarsening of relative reachability.
2. **M. Steinmetz, J. Hoffmann. *Towards Clause-Learning State Space Search: Learning to
   Recognize Dead-Ends.* AAAI 2016** (+ *State Space Search Nogood Learning*, AIJ 245, 2017)
   and **J. Daum, Á. Torralba, J. Hoffmann, P. Haslum, I. Weber. *Practical Undoability Checking
   via Contingent Planning.* ICAPS 2016**, with **L. Chrpa, W. Faber, D. Fišer, M. Morak.
   *Universal and Uniform Action Reversibility.* KR 2021** and **J. Med, M. Morak, L. Chrpa,
   W. Faber. *Non-deterministic Action Reversibility: Complexity Results.* KR 2025.**
3. **B. Bittner, M. Bozzano, R. Cavada, A. Cimatti et al. *The xSAP Safety Analysis Platform.*
   TACAS 2016** — and, more damagingly, the HAZOP/FMECA tradition it formalises, in which a
   *deviation* from design intent is classified by *consequence severity* as a matter of course.

**Verdict: INCREMENTAL.**

The trichotomy is a decision tree over two predicates the paper does not own: "is a hazard
reachable within *b*" (Cat) and "is the goal reachable within *b*" (Fut). Theorem 5.2
(Partition) — disjointness and exhaustiveness — is immediate from the `if/else if/else`
structure of Def. 5.1 and will be read by any reviewer as true by construction; the paper
currently offers no result that the classes are anything more than that Cartesian product.
NOVELTY-v2 flagged exactly this and asked for a structural theorem (equivalence classes of a
preorder on post-deviation states; or Futile decidable strictly more cheaply than Cat). **That
theorem is still missing, and its absence is now the paper's most quotable weakness.** The
"point of no return" is dead-end detection under a different name — the paper says so, which
helps — but the *lifting to a protocol node* is a re-indexing, not a new analysis. The one
thing here that survives contact with the literature is the deliberate refusal to collapse
Futile into Catastrophic, i.e. "failure is not disaster"; that is a **framing** contribution,
and framing contributions do not survive an ECOOP rebuttal on their own.

---

## Claim 3 — `T-Choice-Safe`: one syntax-directed rule, sound **and** complete

**Closest prior work**

1. **M. Naik, J. Palsberg. *A Type System Equivalent to a Model Checker.* ESOP 2005; ACM TOPLAS
   30(5):29, 2008.**
2. **N. Kobayashi, C.-H. L. Ong. *A Type System Equivalent to the Modal Mu-Calculus Model
   Checking of Higher-Order Recursion Schemes.* LICS 2009.**
3. **S. Eriksson, G. Röger, M. Helmert. *Unsolvability Certificates for Classical Planning*
   (ICAPS 2017) and *A Proof System for Unsolvable Planning Tasks* (ICAPS 2018).** The
   "refutation asymmetry" the paper leans on — a *no* answer must be independently checkable —
   is a solved and named problem in planning, with a sound and complete certificate calculus.

**Verdict: INCREMENTAL.**

The paper already concedes ("we do not present this as deep — the rules are the reachability
relation with the negation pushed through"). That concession is correct and should stay, but
it costs C2 its status as a headline contribution. Two additional pressures the paper does not
anticipate. First, Naik–Palsberg does not merely set the template: it *pre-empts the rebuttal*
("types explain why a program is accepted; model checkers why one is rejected"), which the
paper reuses in §8 without attributing that specific move. Second, the argument that
completeness makes a refutation "a genuine risk" is exactly the unsolvability-certificate
argument, and Eriksson et al. did it with a verified checker; if the paper wants credit for
"a failure is never an artifact of conservative rules" it must position against them. The
rule is new as a rule; the *result type* is 20 years old and the *use* of the result type is 9.

---

## Claim 4 — The bridge: typed sessions, budget distribution, μ, bystanders

**Closest prior work**

1. **A. D. Barwell, A. Scalas, N. Yoshida, F. Zhou. *Generalised Multiparty Session Types with
   Crash-Stop Failures.* CONCUR 2022, LIPIcs 243:35** (journal: LMCS 2025) and **A. D. Barwell,
   P. Hou, N. Yoshida, F. Zhou. *Designing Asynchronous Multiparty Protocols with Crash-Stop
   Failures.* ECOOP 2023, LIPIcs 263:1 (Distinguished Paper).** A generalised MPST typing
   system **parametric on a behavioural safety property**, with optional reliability assumptions
   spanning fully-reliable to fully-unreliable, and validation by mCRL2 model checking.
2. **D. Tirore, J. Bengtson, M. Carbone. *Multiparty Asynchronous Session Types: A Mechanised
   Proof of Subject Reduction.* ECOOP 2025, LIPIcs 333:31.**
3. **M. Viering, R. Hu, P. Eugster, L. Ziarek. *A Multiparty Session Typing Discipline for
   Fault-Tolerant Event-Driven Distributed Programming.* PACMPL 5(OOPSLA):229, 2021** — party
   replacement and segment retry under unreliable failure detection.
4. **M. A. Le Brun, O. Dardha. *MAGπ: Types for Failure-Prone Communication.* ESOP 2023, LNCS
   13990, pp. 363–391** (and *MAGπ!*, COORDINATION 2024) — non-Byzantine faults incl. loss,
   reordering, crash and partition, with per-participant reliability.
5. **P. Hou, N. Lagaillardie, N. Yoshida. *Fearless Asynchronous Communications with Timed
   Multiparty Session Protocols.* ECOOP 2024, LIPIcs 313:19** — affinity + timeouts +
   time-failure handling in one MPST theory.

**Verdict: NOVEL-IN-COMBINATION. This is the paper's real contribution and should be its
headline.**

Nothing in the MPST literature carries a **quantity that an unreliable participant spends**
through subject reduction. Barwell et al. is the closest and it is close in *shape* only: their
fault is a crash (the participant stops and its type becomes `stop`), the property is a
parameter validated externally, and there is no counter, no world, no goal. The instrumented
head-step semantics (`hstep`) whose cost is debited exactly, `budget_distributes` (a global
budget split into per-role allowances that are jointly sound), and the cost-preserving
simulation `sim_step`/`bridge_mu` for recursive sessions are, as far as this sweep can tell,
without precedent. The bystander theorem is the weaker half: swapping independent adjacent
interactions is Honda–Yoshida–Carbone/Deniélou–Yoshida-era, and world-effect independence is
partial-order reduction's independence relation (Godefroid; Chapman's 1987 commuting actions);
the *combination* — subject reduction under permutation whose side conditions are STRIPS
footprint disjointness, needed precisely because the property is order-sensitive — is new, but
it is a lemma-shaped contribution, not a headline.

**The attack to prepare for.** Scalas (co-author of CONCUR 2022, of *Less is More* POPL 2019,
and of NEST at ECOOP 2026) will ask: *instantiate your k-tolerance as our behavioural safety
property φ over a product LTS, and doesn't the bridge follow from our generalised typing system
for free — asynchronously, which yours is not?* The paper needs a prepared answer. The honest
one is that their φ ranges over *typing contexts* and cannot see the world or a counter, so
k-tolerance is not in the parameter's domain without adding the product to the context itself
— which is precisely the whole-system move §8 argues against. Say that explicitly.

---

## Claim 5 — Decidability via Node × World × {0..k}; finite μ-closure; extracted kernel

**Closest prior work**

1. **R. Ehlers, U. Topcu, HSCC 2014** (again): the counter-product with decrementing edges is
   the same construction, for the same purpose.
2. **D. Aineto et al., ECAI 2023 / C. Domshlak, *Fault Tolerant Planning: Complexity and
   Compilation*, ICAPS 2013**: compile a *k*-failure budget into a FOND / classical task by
   carrying the counter in the state.
3. **A. Suresh, N. Yoshida. *Unreliability in Practical Subclasses of Communicating Systems.*
   FSTTCS 2025, LIPIcs 357:52** — decidability of the practical MPST subclasses (RSC, k-MC)
   *under failure models*, with complexity bounds preserved.
4. **D. Tirore, J. Bengtson, M. Carbone, ECOOP 2025**; **D. Castro-Perez, F. Ferreira, N.
   Yoshida, *Zooid*, PLDI 2021** — finiteness of the unfolding closure for regular types is
   routine in mechanised MPST.

**Verdict: INCREMENTAL. Technique SCOOPED; the mechanisation is credibility, not contribution.**

NOVELTY-v2 already said `cands_closed` is a supporting lemma; that is right and the paper says
so. The sharper problem is Prop. 9.7 (tolerance degree, PSPACE, iterate the decider): this is
the standard budgeted-reachability construction and a reviewer from the synthesis side will
recognise it on sight from Ehlers–Topcu. Do not let Theorem 9.5/9.6 read as a contribution.
Two specific exposure points: (i) the reversibility complexity caveat is cited (Med et al. KR
2025) but the paper's escape — "the widened finite-range fragment the checker already commits
to" — is a *fragment restriction stated in one clause*, and a PSPACE claim resting on an
unstated fragment is the kind of thing a careful PC member will challenge; (ii) Suresh &
Yoshida is the current state of the art on "decidability of MPST subclasses under a fault
model" and is not cited, which reads as unawareness of the immediate neighbourhood.

---

## Claim 6 — Modular sequential composition against an interface

**Closest prior work**

1. **L. Gheri, N. Yoshida. *Hybrid Multiparty Session Types: Compositionality for Protocol
   Specification through Endpoint Projection.* PACMPL 7(OOPSLA1):112–142, 2023.** The first
   semantics-preserving MPST theory of multiparty compositionality, with hybrid types for
   sub-protocols, a compatibility relation, and composition preserving liveness and
   deadlock-freedom.
2. **F. Barbanera, I. Lanese, E. Tuosto. *Composition and Decomposition of Multiparty Sessions.*
   JLAMP 119:100620, 2021** (with *Choreography Automata*, COORDINATION 2020) — composition of
   sessions via coupled gateways, with the composed global type computable from the components'.
3. **D. Castro-Perez, F. Ferreira, S.-S. Jongmans. *A Synthetic Reconstruction of Multiparty
   Session Types.* PACMPL 10(POPL):50, 2026.** The paper the compositionality argument in §8
   leans on — cited twice under two different keys (see bibliography errors below).
4. Summary-based interprocedural analysis: **M. Sharir, A. Pnueli (1981)**; **T. Reps, S.
   Horwitz, M. Sagiv, POPL 1995**. Cone-of-influence projection: **E. M. Clarke, O. Grumberg,
   D. Peled, *Model Checking*, MIT Press 1999, §. abstraction**.

**Verdict: INCREMENTAL.**

`TC_seq` is "check the second block against the set of exit states of the first" — a procedure
summary, with the "interface form" being a widened summary and the "principled coarsening"
being cone of influence. Both are textbook. The paper's own evaluation (Finding 3) concedes
that the concrete exit set blows up and that only the abstraction makes it pay, which is
honest but also states plainly that the *theorem* is not the contribution; the *abstraction* is,
and the abstraction is 25 years old. In the MPST frame the competition is worse, not better:
Gheri & Yoshida and Barbanera–Lanese–Tuosto are the papers a PC will expect to see cited for
"modular composition of multiparty protocols", and neither appears in the bibliography.
Recommendation: demote Claim 6 to an engineering subsection of §8, keep the exponential-vs-linear
table, and stop calling it a contribution.

---

## Claim 7 — 162 skills; verdicts predict wasted or fabricated runs

**Closest prior work**

1. **J. Dantanarayana, S. Kashmira, L. Tang, J. Mars. *SIGIL: Compiling Agent Skills into Typed
   Harnesses.* arXiv:2607.27309, 2026.** 30 skills, two model generations; a prose agent
   performs only 56% of the steps its own skill mandates; compiling to a typed IR raises that
   to 86%, completes the full procedure 2.3× as often, and uses **0.58× the tokens**. This is
   the "a type discipline over agent skills changes run outcomes and token cost" result,
   already published, with a bigger effect size and a cleaner metric.
2. **D. Xu, Z. Chen, Z. Pan, J. Guan, D. Dong, J. Li, B. Pu. *SkillSmith: Compiling Agent
   Skills into Boundary-Guided Runtime Interfaces.* arXiv:2605.15215, 2026.** Offline
   compilation of skills into minimal executable interfaces; **57.44% reduction in solve-stage
   tokens**, 2.02× faster, on SkillsBench.
3. ***Agent Skills Can Be Harmful: An Empirical Study of Skill-Induced Failures.*
   arXiv:2608.11888, 2026.** Runs on SkillsBench and SWE-Skills-Bench pairing *task
   specifications, skill contents, execution trajectories, verifier outcomes, token use and
   execution time*, with root-cause taxonomies for functional failures **and efficiency
   regressions** — i.e. the paper's Table 8 experiment design, at larger scale.
4. **Y. Wang et al. *Can We Predict Before Executing Machine Learning Agents?* ACL 2026
   (arXiv:2601.05930).** Predicting run outcome *before* execution to skip the run; 61.5%
   accuracy with calibrated confidence, 6× convergence acceleration in ForeAgent.
5. Scale context that will be used against the corpus: **GitSkills: A Dataset of Agent Skills on
   GitHub** (arXiv:2608.10906) — 3,797,117 `SKILL.md` files from 282,200 repositories; and
   *Agent Skills in the Wild* (arXiv:2601.10338), *Malicious Agent Skills in the Wild*
   (arXiv:2602.06547), *Credential Leakage in LLM Agent Skills* (arXiv:2604.03070) for the
   corpus-security scan in §10, which is a smaller replication of published work.

**Verdict: NOVEL-IN-COMBINATION, but the weakest-supported of the three "novel" claims.**

What no one else has: a checker whose **refutations are sound** (the one-act-per-tool reading
under-approximates, so a refutation holds whatever the document means) evaluated by
**recomputing every artifact** so that a fabricated result is counted as such, with the
refuted-run token spend measured against the check's own token cost. The "silent wrong result"
category, verified by recomputation rather than by an LLM judge, is the single most defensible
piece of the evaluation and should be foregrounded. What will be attacked: 8 real skills + 4
authored pairs + 134 runs is small against SkillsBench-scale studies published in the same
year; the five rebuilt tasks are authored by the same people who authored the checker; the
authored specification pairs are constructed so their B-variants must fail, so the 0/16 result
there is close to tautological; and "a checker refuses when the runtime lacks the tool the
skill names, and then the run fails" is a claim a reviewer can restate as trivially true —
the interesting half (the scale-up showing the agent's hand-computation escape route closes)
is one paragraph and rests on five tasks. Also note that Findings 1 and 5 are in mild tension
(Finding 1: the corpora contain no choice points and no irreversible tools, so the severity
half is invisible to them; Finding 5: those same corpora carry the empirical weight) — a
reviewer will ask which half of the paper the 162 skills actually evaluate. The answer is *the
achievability half, not the severity half*, and the paper should say so in one sentence rather
than let the reader find it.

---

## (a) The three citations most likely to be used against the paper at ECOOP

1. **R. Ehlers, U. Topcu. *Resilience to Intermittent Assumption Violations in Reactive
   Synthesis.* HSCC 2014.** *(with B. Bloem, K. Chatterjee, K. Greimel, T. A. Henzinger, B.
   Jobstmann, Acta Informatica 51(3–4), 2014, and R. Meira-Góes, I. Dardik, E. Kang, S.
   Lafortune, S. Tripakis, CAV 2023 as the supporting cluster.)* This is the new most dangerous
   citation and it is **absent from the paper entirely**. It owns: a budget of *k* deviations,
   tolerated; the counter-product decision procedure; and the "largest tolerated deviation" as
   the reported quantity. A reviewer who cites it reduces Claims 1, 3 and 5 to "Ehlers–Topcu,
   presented as inference rules, on session types". The rebuttal exists (their deviation is an
   *environment* assumption violation; ours is a *typed participant's own selection*, and it is
   carried to programs by subject reduction, which synthesis has no analogue of) — but the
   rebuttal must be *in the paper*, not in the response letter.

2. **A. D. Barwell, A. Scalas, N. Yoshida, F. Zhou. *Generalised Multiparty Session Types with
   Crash-Stop Failures.* CONCUR 2022 / LMCS 2025** (with the ECOOP 2023 Distinguished Paper).
   Cited, but with the **wrong author list** (the bibliography prints "Barwell, Hou, Yoshida,
   Zhou" for CONCUR 2022 — that is the ECOOP 2023 list; Scalas is the CONCUR co-author). Getting
   a likely reviewer's name wrong on the paper you are positioning against is a gift. On
   substance: their typing system is *parametric on a behavioural safety property*, which is
   exactly the socket k-tolerance appears to fit into, and they get asynchrony, a tool, and a
   distinguished-paper precedent that the community accepts this move.

3. **M. Naik, J. Palsberg. *A Type System Equivalent to a Model Checker.* ESOP 2005 / TOPLAS
   30(5):29, 2008.** Unchanged from v2 and still lethal for C2 — it makes Theorem 7.1 an
   instance of a known template, on more mainstream programs, and it already contains the
   standard rebuttal to "so what, it's model checking", so that rebuttal cannot be presented
   as this paper's insight.

*Runner-up, and the one that will sting most in the rebuttal round:* **P. Yu, S. Zhu, G. De
Giacomo, M. Kwiatkowska, M. Y. Vardi. *The Trembling-Hand Problem for LTLf Planning.* IJCAI
2024** — the identical fault model ("faults or imprecision in its action selection mechanism"),
named, published two years earlier, by five very well-known people. It is probabilistic and
goal-directed rather than budgeted and hazard-directed, which is a real difference and an easy
paragraph. Not citing it is the kind of omission that reads as either unawareness or evasion.

---

## (b) The single weakest claim

**Claim 2 — the Benign / Futile / Catastrophic partition.** It is the paper's advertised
*analytic payload* ("the middle one is what existing disciplines cannot express"), and it is
the claim with the least formal content: Def. 5.1 is a two-branch decision tree over
`reach_haz` and `reach_goal`, and Theorem 5.2 (disjoint + exhaustive) is immediate from that
shape. Every one of the three classes has an owner elsewhere — Cat is hazard reachability, Fut
is dead-end detection (Steinmetz & Hoffmann) or relative-reachability collapse (Krakovna et
al.), the point of no return is undoability checking (Daum et al.; Chrpa et al.; Med et al.),
and "classify a deviation by consequence severity" is HAZOP/FMECA formalised by xSAP. The
paper's defence — that here severity is *computed* rather than analyst-supplied — is correct
and is stated in one sentence; it is not enough to carry a contribution. **This is the second
audit in a row to ask for a structural theorem about the trichotomy and not get one.** Either
supply one (Futile strictly cheaper to decide than Catastrophic would do; or the classes as
equivalence classes of a natural preorder on residuals; or a lattice/monotonicity result
relating severity to budget) or demote the partition from "analytic payload" to "definitional
apparatus" and let Claim 4 carry the paper. *Runner-up: Claim 6, which is a procedure summary
with cone-of-influence abstraction and should stop being listed as a contribution.*

---

## (c) Honest verdict: is the core contribution novel enough for ECOOP 2027?

**Borderline accept, contingent on repositioning — and, as the draft currently stands, closer
to a reject than the paper thinks.** The defensible core is narrow but real: *a behavioural
type theory whose fault is a typed participant's own selection at a protocol branch, budgeted,
where the budget is spent by the participant and carried to programs by a cost-preserving
subject reduction that distributes over roles and survives recursion and independent
permutation, mechanised axiom-free.* No paper found in this sweep does that; the MPST fault
literature is uniformly about participants that *stop* (crash-stop, affine, timeout, escape,
replacement), and the deviation-budget literature (synthesis, planning) has no type system, no
participants, and no program-level guarantee. That is a genuine gap and ECOOP is the right
venue for it. The danger is that the paper currently spreads its weight across seven claims of
which four (2, 3, 5, 6) are instances of known templates that the paper either concedes to be
shallow or does not cite the owner of, and one (7) sits in a 2026 agent-skills literature that
is moving faster and at larger scale than the evaluation. A PC that reads C1–C5 as listed will
find at most one contribution per reviewer and conclude "an application paper with a
mechanisation". A PC that reads the paper as *one* theorem (the budgeted bridge) with the
severity partition as definitional apparatus, the decision procedure as engineering, and the
evaluation as non-vacuity evidence, will find a clean, well-mechanised, correctly-scoped ECOOP
paper. The single most valuable edit is not new theory: it is adding the reactive-synthesis
robustness cluster to §12 with an explicit two-sentence delta, fixing the Barwell author list,
and rewriting the contributions list so that C3 is the headline and C1/C2/C4/C5 are its
supporting apparatus.

---

## (d) Missing related-work citations the paper must add

Checked against the 51 entries currently in `\begin{thebibliography}`; none of the following
appears there.

**Must add — these are the ones whose absence is a defect:**

- R. Ehlers, U. Topcu. *Resilience to Intermittent Assumption Violations in Reactive Synthesis.*
  HSCC 2014, ACM, 203–212.
- R. Bloem, K. Chatterjee, K. Greimel, T. A. Henzinger, B. Jobstmann. *Synthesizing Robust
  Systems.* FMCAD 2009; Acta Informatica 51(3–4):193–220, 2014.
- C. Zhang, D. Garlan, E. Kang. *A Behavioral Notion of Robustness for Software Systems.*
  ESEC/FSE 2020, 1–12. **and** R. Meira-Góes, I. Dardik, E. Kang, S. Lafortune, S. Tripakis.
  *Safe Environmental Envelopes of Discrete Systems.* CAV 2023, LNCS 13965, 349–370.
- P. Yu, S. Zhu, G. De Giacomo, M. Kwiatkowska, M. Y. Vardi. *The Trembling-Hand Problem for
  LTLf Planning.* IJCAI 2024, 3630–3638.
- M. Viering, R. Hu, P. Eugster, L. Ziarek. *A Multiparty Session Typing Discipline for
  Fault-Tolerant Event-Driven Distributed Programming.* PACMPL 5(OOPSLA):229, 2021.
- M. A. Le Brun, O. Dardha. *MAGπ: Types for Failure-Prone Communication.* ESOP 2023, LNCS
  13990, 363–391.
- P. Hou, N. Lagaillardie, N. Yoshida. *Fearless Asynchronous Communications with Timed
  Multiparty Session Protocols.* ECOOP 2024, LIPIcs 313:19.
- A. Suresh, N. Yoshida. *Unreliability in Practical Subclasses of Communicating Systems.*
  FSTTCS 2025, LIPIcs 357:52. *(directly bears on §9's decidability claim and on the k-MC
  naming footnote)*
- L. Gheri, N. Yoshida. *Hybrid Multiparty Session Types: Compositionality for Protocol
  Specification through Endpoint Projection.* PACMPL 7(OOPSLA1):112–142, 2023. **and**
  F. Barbanera, I. Lanese, E. Tuosto. *Composition and Decomposition of Multiparty Sessions.*
  JLAMP 119:100620, 2021. *(both for §8/Claim 6)*
- J. Dantanarayana, S. Kashmira, L. Tang, J. Mars. *SIGIL: Compiling Agent Skills into Typed
  Harnesses.* arXiv:2607.27309, 2026. *(Finding 6's token argument has a published competitor)*

**Should add:**

- V. Krakovna, L. Orseau, R. Ngo, M. Martic, S. Legg. *Penalizing Side Effects using Stepwise
  Relative Reachability.* IJCAI-AISafety 2018 (CEUR 2419) / *Avoiding Side Effects By
  Considering Future Tasks*, NeurIPS 2020. *(§5 severity)*
- S. Eriksson, G. Röger, M. Helmert. *Unsolvability Certificates for Classical Planning.* ICAPS
  2017; *A Proof System for Unsolvable Planning Tasks.* ICAPS 2018. *(§7 refutation asymmetry)*
- L. Chrpa, W. Faber, D. Fišer, M. Morak. *Universal and Uniform Action Reversibility.* KR 2021.
  *(§5 irreversibility)*
- A. Rovetta, D. Aineto, A. E. Gerevini, E. Scala, I. Serina. *Improving Resilient Planning
  Through Landmarks and Regressed State Formulas.* ECAI 2025. *(current state of K-resilience)*
- B. Mohammadi, L. Bindschaedler. *The Irreversibility Budget: Fleet-Level Risk Accounting and
  Admission Control for Agent Operating Systems.* AgenticOS @ SOSP 2026, arXiv:2609.00275.
  *(an "irreversibility budget" for agents already exists as a name; distinguish it — theirs is
  runtime admission control priced in value-at-risk, ours is a static well-formedness condition)*
- D. Xu et al. *SkillSmith: Compiling Agent Skills into Boundary-Guided Runtime Interfaces.*
  arXiv:2605.15215, 2026; *Agent Skills Can Be Harmful: An Empirical Study of Skill-Induced
  Failures.* arXiv:2608.11888, 2026; *GitSkills: A Dataset of Agent Skills on GitHub.*
  arXiv:2608.10906, 2026. *(§10 scale and design context)*
- A. Metere. *Skills as Verifiable Artifacts: A Trust Schema and a Biconditional Correctness
  Criterion for Human-in-the-Loop Agent Runtimes.* arXiv:2605.00424, 2026. *(companion to the
  already-cited `metere-skills`; it is the paper that argues the human gate must fire on every
  irreversible call, which is the premise §5 relaxes)*
- Optional, for the supervisory-control paragraph: A. Paoli, S. Lafortune, *Safe Diagnosability
  for Fault-Tolerant Supervision of Discrete-Event Systems*, Automatica 41(8), 2005; Q. Wen,
  R. Kumar, J. Huang, *Fault-Tolerant Controllability*, ACC 2008.

**Bibliography defects to fix before submission (all verified this sweep):**

1. `barwell-concur22` — authors are **A. D. Barwell, A. Scalas, N. Yoshida, F. Zhou** (CONCUR
   2022, LIPIcs 243:35). The printed "Barwell, Hou, Yoshida, Zhou" is the ECOOP 2023 list.
2. `castro-popl26` and `synthetic-pacmpl26` are **the same paper**, cited twice under two keys
   with both halves marked "[to verify]": D. Castro-Perez, F. Ferreira, S.-S. Jongmans,
   *A Synthetic Reconstruction of Multiparty Session Types*, PACMPL 10(POPL):50, 2026
   (DOI 10.1145/3776692). Merge them.
3. `morak-kr25` — authors are **J. Med, M. Morak, L. Chrpa, W. Faber**, *Non-deterministic
   Action Reversibility: Complexity Results*, KR 2025 (proceedings.kr.org/2025/45).
4. `pact` — verified: K. Gopinathan et al., *Pact: A Choreographic Language for Agentic
   Ecosystems*, arXiv:2605.03143, presented at CP 2026 (2nd Int. Workshop on Choreographic
   Programming). It is a *workshop* paper; say so, since it is the only work that owns the
   "choreography with first-class agent choice" framing and the paper should not overstate its
   weight.
5. `agentltl` — verified as arXiv:2607.02599, *AgentLTL: A Trace-Verification Framework for
   Measuring, Enforcing, and Training Procedural Compliance in Tool-Using LLM Agents*.
6. `trac-facct26` — the arXiv/venue title is *Formal Methods Meet LLMs: Auditing, Monitoring,
   and Intervention for Compliance of Advanced AI Systems* (arXiv:2605.16198); authors
   P. A. Alamdari, T. Q. Klassen, S. A. McIlraith, FAccT 2026. Correct as printed.
7. `etas` — verified as arXiv:2607.17780; authors still to be filled in.

---

## One further framing note

§12 currently opens with "MPST with a fault model" and never leaves the behavioural-types
neighbourhood except for a planning paragraph. The three most dangerous citations found in this
sweep are in **reactive synthesis** and **software-engineering robustness**, and one is in
**planning under action-selection error**. A hostile ECOOP reviewer with a formal-methods
background — which describes most of the PC — will find them in ten minutes. Add a
"Deviation budgets and robustness" paragraph to §12 that names Ehlers–Topcu, Bloem et al.,
Zhang–Garlan–Kang / Meira-Góes et al. and Yu et al., states the delta in two sentences (the
deviation is the *typed participant's own selection*, the target is a *hazard* not the goal,
and the budget is carried to *programs* by subject reduction), and the paper stops looking
like it discovered a wheel.
