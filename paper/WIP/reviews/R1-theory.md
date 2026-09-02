# ECOOP review — R1 (theory and mechanization only)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that Choose Wrongly*
**Reviewer expertise:** behavioural types, MPST, concurrency, mechanized metatheory.
**Scope of this review:** Sections 3–10 and 12, and `proof/Severity.v`, `Bridge.v`, `Mu.v`, `Regular.v`, `Interleave.v`, `Repairs.v`, `Kernel.v`. I did **not** assess Section 8 (evaluation); another reviewer has it. Line numbers refer to `main.tex` and to the `.v` files as of commit `61b878e` ("Round 1 of review: progress under misselection, and a readable abstract"). I read every Coq file named above in full, not just the theorem statements.

---

## (a) Summary judgement

**Score: C — weak reject. Confidence: 4/5 (high on the Coq reading, high on the type-theory critique; no opinion on the evaluation).**

The reframing is the best idea I have seen in this space: refusing to prevent wrong choices and instead separating *futile* from *catastrophic* is the right axis, and "failure is not disaster" is a slogan worth a paper. The artifact is real — 93 `Print Assumptions`-closed results, stdlib only, no `Admitted`, no `Axiom` (I checked). `Mu.v` in particular contains genuine work.

But the paper does not currently survive the question a session-types PC asks, and it fails in exactly the way its own §11 congratulates itself for having caught in the predecessor draft: **the payoff theorems are vacuous where they matter**.

Three concrete instances, all mechanically checkable and all in the artifact right now:

1. Both exactly-characterized repairs (guard, reorder-at-the-PNR) achieve `⊢_k` by making the head capability **disabled**, and a disabled capability is not conformable: `CT_Act` (`Bridge.v:54–58`, `Mu.v:554–558`) carries the premise `(exists W', E a W W')`. So in precisely the worlds where the repair does its work, **no session conforms to the repaired protocol**, and Theorem 6 (Bridge) and Theorem 7 (Progress) say nothing about it. The paper simultaneously asserts "a typed session that has not finished can always take a head step" (thm:progress, l.620) and "a misselected guarded branch is stuck" (thm:guard, l.1233). Those two are only consistent because the second describes a configuration the first says does not exist.
2. `CT_Goal` (`Bridge.v:50–53`, `Mu.v:552`) requires `phi W` on **every** branch of a choice, misselected branches included. Under the paper's own default rational-choice guard (a branch is a misselection iff it forfeits the goal, l.432–440), a goal-marked protocol with a misselectable branch has **no conformant session at all**. The `✓φ` construct is advertised in §3 as part of the base discipline and is inert in `safeT` (T-Goal, l.547, drops φ entirely).
3. There is **no non-vacuity result anywhere in the development**. I grepped: no inhabitation lemma, no canonical-session construction, no `exists s. ctypes G s W` for any class of `G`. The predecessor draft was withdrawn because `DeviationLayer.v` found a premise that could not be satisfied; nothing in the present artifact would catch the same bug again.

On top of that, the paper's answer to "why is this a type system and not a reachability check" is currently *rhetoric* (§6, l.567–578; §9), not structure. The pieces of a real answer are already lying in the artifact unnamed — `tolerance_downward_closed` is budget subsumption, `repair_narrow_sound` is internal-choice covariance, `kernel_first_spec` is a minimal-budget/principality result — and the paper does not use any of them.

I would be happy to see this at ECOOP after a revision. The theory is not broken beyond repair; it is under-stated in the places that are hard and over-stated in the places that are easy. Items W1–W3 plus one of W9's sub-items would move me to **B**, and I say so explicitly so the authors know the target.

---

## (b) Three strengths

**S1. The trichotomy has actual formal content, not just a name.** Most papers that introduce a severity classification stop at the definition. `severity_monotone_in_budget` (`Severity.v:352`) plus `tolerance_degree_is_a_threshold` and `catastrophic_upward`/`futile_downward` establish that Futile/Benign/Catastrophic are three *consecutive intervals* of budgets and that `k*` is a genuine threshold rather than the point at which a search gave up. That is the difference between a taxonomy and a theorem, and the paper is right to lead with it (C3, l.276). `reach_mu_iff_run` (`Mu.v:689`) doing the extra work of making the classes statements about *runs* rather than about a fixpoint is the correct instinct and rarely bothered with.

**S2. `Mu.v` is the real contribution and it is genuinely hard.** `subst_comp` (l.302), `unfold_close` (l.344), the `good`/`okst` invariant (l.386–528) and `cands_closed` (l.529) constitute a de Bruijn-indexed proof that the unfolding closure of a closed regular type is finite and step-closed, with `reach_in_cands` (l.538) tying it to the product. `Regular.v` is stated abstractly over any node/world types with successor-closure hypotheses (`nodes_closed`, `worlds_closed`, l.490–493) rather than baking in a fragment, which is the right level of generality and makes the `Kernel.v` instantiation cheap. This is the strongest mechanized content in the artifact.

**S3. The scope honesty is unusually good for a draft.** §11 reporting the mechanized refutation of the authors' own predecessor design is exemplary and I hope it survives to camera-ready. §12 naming the head-move/synchronous restriction and volunteering the comparison to Tirore et al. [ECOOP'25] is the right instinct. thm:exact declining to call itself deep (l.567) is correct and disarms the obvious objection. Per-file `Print Assumptions` harnesses (`check_*.v`) rather than a single blanket claim is the right discipline.

---

## (c) Weaknesses

### W1 — **BLOCKING.** The two "exactly characterized" repairs are safe because they are dead, and no session conforms to them

`validates a psi` is defined (`Repairs.v:23`) as `forall W W', E a W W' <-> (psi W /\ W' = W)`. So when `¬psi W`, the relation `E a W _` is **empty**.

- `guard_absorbs_misselection` (`Repairs.v:32`) then proves `safeT c (GAct a p Gl) W` **vacuously**: `ST_Act`'s premise `forall W', E a W W' -> safeT b G W'` has no instances.
- `repair_reorder_pnr` (`Repairs.v:166`) proves "the reordered protocol is typable at every budget" by exactly the same move: `¬psi W` kills `chk`.

Both are fine as statements about `safeT`. They are not fine as *repairs*, because the conformance judgment cannot type the repaired protocol in those worlds:

```coq
| CT_Act : forall a p G s W P,
    s p = PAct a P ->
    (exists W', E a W W') ->            (* Bridge.v:56 — this is the killer *)
    (forall W', E a W W' -> ctypes G (supd s p P) W') ->
    ctypes (GAct a p G) s W
```

and `CT_Comm` (`Bridge.v:59–70`) demands `ctypes Gl _ W` for *every* branch at the *same* `W`. So `ctypes (GComm p q ((l,psi,GAct a p Gl)::brs)) s W` is underivable whenever `¬psi W` — which is the only case thm:guard is about. Same for `Mu.v:554`.

Consequences the paper must confront:
- thm:bridge (l.609), thm:progress (l.620) and thm:bridge-mu (l.655) have empty hypotheses on guard-repaired and reorder-repaired protocols in the failing worlds.
- thm:guard's gloss "a misselected guarded branch is stuck, so it costs budget but reaches nothing" (l.1233–1240) describes a session configuration that thm:progress asserts cannot exist. As written the two theorems read as a contradiction; a reader has to reconstruct the resolution ("the configuration is untypable") themselves, and the resolution is worse than the apparent contradiction.
- The evaluation reports guard-repaired protocols as `k*≥5` (Table 1, `email_campaign_guarded`; l.898) and Finding 4 says "repairs remove the catastrophes". Under the current definitions the correct reading is "the repaired protocol has no conformant session where the guard fails", which is not the same claim.

**Concrete fix (pick one, and say which):**
(a) Drop `(exists W', E a W W')` from `CT_Act`/`CT_Comm`, restate `progress` as *"either a head step exists, or the head is a disabled capability"*, and add a separate theorem `blocked_is_not_hazardous`: a blocked configuration reachable within budget satisfies `¬Haz`. This is the smallest change and it is the honest one: blocking **is** the repair mechanism, so make it a first-class outcome instead of an absence.
(b) Model validation as a two-branch construct `chk?{ok. G ; abort. R}` so the repaired protocol stays live, and reprove `repair_guard_exact` on it. More work, but it keeps deadlock-freedom, which is what a session-types audience will actually want.
(c) At minimum, state in §10 that guard and reorder trade progress for safety, and that the bridge theorem does not apply to the repaired protocol in the worlds where the guard fails. This is not sufficient for acceptance but it is the minimum honest disclosure.

Note the shape: a premise `exists W'. E a W W'` that cannot be satisfied is *structurally identical* to `AUDIT.md` Finding 1 (`T-Quar` needs `G ↾ p` defined; it is not), which the authors correctly call blocking.

### W2 — **BLOCKING.** No non-vacuity / inhabitation result anywhere

Nothing in the artifact proves that `ctypes` is inhabited for any interesting class of protocols. Given W1 and W3 this is not a formality: the paper's central theorem is an implication whose antecedent may be empty on the paper's own running structures, and the development has no way to notice.

**Concrete fix.** Define the canonical session `erase(G)` (the obvious projection-free erasure: `GComm p q brs ↦ p:POut q [(l, erase Gl)], q:PIn p [...]`, `GAct a p G ↦ p:PAct a (erase G)`) and prove

```coq
Theorem ctypes_inhabited :
  forall G W, wf G W -> ctypes E (erase G) W.
```

for an explicit `wf` (whatever side conditions you need: `p <> q`, `brs <> nil`, enabledness of every action at every reachable world, goal markers satisfied). Add it to `check_bridge.v`. Then — this is the point — **run it against the repaired protocols of §10 and against every protocol in Table 1**. If it fails on the guard-repaired ones, you have found W1 yourself and can present the resolution instead of me presenting the problem. If `wf` has to be so strong that it excludes the interesting cases, that is a result and should be reported.

A paper that devotes §11 to "our predecessor was vacuous and we caught it" must ship the check that catches it.

### W3 — **MAJOR.** Goal markers `✓φ` are simultaneously over-demanded and inert

Three symptoms of one confusion:

1. `T-Goal` (l.547) has premises `W ⊭ Haz` and `⊢_b G,W` — **φ is not mentioned**. `RH_goal` (`Severity.v`) likewise ignores it. So `✓φ` nodes contribute nothing whatsoever to the well-formedness condition. Delete every `✓φ` from a protocol and `⊢_b` is unchanged.
2. `CT_Goal` (`Bridge.v:50`, `Mu.v:552`) requires `phi W`, and because `CT_Comm` demands conformance of *every* branch at the choice world, a protocol that marks its goal after a choice with a goal-losing branch is **untypable**. Under the paper's default rational-choice guard (l.432–440: a misselection *is* a choice that forfeits the goal) that is exactly the class of protocols the paper is about.
3. The severity goal `Φ` (`Severity.v` `Section Severity`, `Variable Phi`) is a *separate parameter*, formally unrelated to any `✓φ` in the syntax. §5 (l.474) says "Let φ be the goal" immediately after §3 introduced `✓φ` as the goal marker. A reader will assume they are the same φ. They are not, in any file.

**Concrete fix.** Decide what `✓φ` is for. If it is a specification marker, make `CT_Goal` premise-free and add a separate *liveness* obligation (`every complete run satisfies its markers`) that is allowed to fail under misselection — which is precisely what \Fut means, and would connect the marker to the severity classes for the first time. If it is a runtime assertion, say so and accept that goal-marked protocols with losable goals are untypable, and remove `✓φ` from every example. Either way, state the relation between the syntactic `✓φ` and the semantic `Φ` as a definition, and either prove `Φ`-reachability agrees with marker satisfaction or say plainly that they are independent inputs.

### W4 — **MAJOR.** Definition 2's environment-controlled choice has zero mechanization

Definition 2 (l.441–456) ends: *"Choices marked as controlled by the environment are resolved demonically at no cost."* There is **no such construct anywhere in the Coq**. `Gt` (`Severity.v:52–56`) and `Gr` (`Mu.v:111`) have `GComm`/`RComm` with guards and nothing else; `grep -ni "environment\|demonic\|GEnv"` over `Severity.v Mu.v Regular.v Bridge.v Kernel.v Repairs.v Interleave.v` returns nothing. Meanwhile Table 1 lists `order_fulfilment (environment choice)` as a benchmark row with `k*=0`, and §12 lists "environment choices" among what "remain trusted" — which is a limitation about the *kernel*, not a disclosure that the *semantics itself* is unmechanized.

In a paper whose whole pitch is "mechanized end to end, axiom-free", a sentence of the core operational definition with no formal counterpart, exercised by a benchmark row, is a hypothesis smuggled.

**Concrete fix.** Either (a) add `GEnv : Role -> list (Lab * Gt) -> Gt` with the demonic rule `RH_env : In (l,Gl) brs -> reach_haz b Gl W -> reach_haz b (GEnv r brs) W`, a matching `ST_Env` (∀-quantified over branches, same budget), and re-run `TC_exact`, `bridge_step`, `bridge_run` — this is an afternoon's work and closes the gap; or (b) delete the sentence from Definition 2 and state in §8 that environment choice is an implementation feature outside the theory. (a) is much better: the demonic branch is the one place where the budget genuinely should *not* be debited, and it is a nice contrast to the misselection rule.

### W5 — **MAJOR.** "Budgets distribute over participants" is a fold identity, presented as the cross-participant composition result

`budget_distributes` (`Bridge.v:347`) is proved in eight lines. Its content is `total_eq_sum_percost` (`Bridge.v:329`) — *the sum of a list of costs equals the sum over roles of the per-role subsums* — followed by `apply bridge_run`. `total_eq_sum_percost` is pure list arithmetic (`sumR_split`, `sumR_indicator`), true of any labelled trace with any cost function whatsoever. It has nothing to do with sessions, types, budgets or misselection.

The text (l.636–648) calls this "the cross-participant composition result: the global budget is a contract that can be split among participants and checked per participant". Nothing is checked per participant. The paper is explicit (l.408) that there are **no local types and no projection**, so there is no per-role judgment for an allowance to index. C1 (l.263) repeats the claim.

**Concrete fix.** Either downgrade: delete the theorem environment, keep one sentence ("the trace cost decomposes by role, so a global allowance can be presented as per-role allowances"), and stop calling it composition. Or do the real thing, which is a genuine contribution if you do it: annotate the conformance judgment with a per-role allowance, `Γ; H ⊢^{k̄} G ⊳ (𝕄; W)`, prove that a role's steps only debit its own component, and prove a *composition* theorem — given `⊢^{k̄₁}` for one subsystem and `⊢^{k̄₂}` for another with `k̄₁ + k̄₂ ≤ k̄`, the composite conforms. That is the theorem the title promises.

### W6 — **MAJOR.** thm:compensate misstates the mechanization in two ways

Paper (l.1254): *"Appending a recovery path `R` to a residual `G_ℓ` is `k`-safe **iff** `R` is safe at every interface point of `G_ℓ`"*.

Coq (`Repairs.v:185`):

```coq
Theorem repair_compensate_sound : forall b Gl R W,
  safeT E Haz b Gl W ->                                        (* hypothesis the paper drops *)
  (forall b' W', ends E b Gl W b' W' -> safeT E Haz b' R W') ->
  safeT E Haz b (gseq Gl R) W.                                 (* one direction only *)
```

The paper's "iff" is a one-directional implication in Coq, and the paper omits the hypothesis `safeT b Gl W` entirely. As stated in the paper the claim is false (take `G_ℓ` itself hazardous and `R = End` with no interface points). The converse is presumably provable — `gseq` is structural — but it is not proved.

**Concrete fix.** Restate as: *"If `⊢_k G_ℓ,W` and `⊢_{b'} R,W'` at every interface point `(b',W')` of `G_ℓ` from `k`, then `⊢_k G_ℓ;R,W`"*, cite `repair_compensate_sound`, and either prove the converse or drop the word "iff". Same wording check for thm:seq (l.812), which is stated correctly.

### W7 — **MAJOR.** The repairs are proved only at the root; the tool applies them at nested nodes

`repair_narrow_sound` (`Severity.v:465`) is:

```coq
safeT E Haz b (GComm p q brs) W -> safeT E Haz b (GComm p q brs') W
```

i.e. narrowing the **top-level** choice. thm:narrow (l.1228) says "removing branches from *a* choice node", and the tool's own output in §2 (l.~300) narrows at a nested path:

```
repair (narrow):
  remove skip_backup at /choice@ops#0
  remove drop_old at /choice@ops#0/skip_backup/choice@ops#1
```

The second of those is not covered by any theorem. Same for `repair_guard_sound`/`repair_reorder_sound`, which are stated for a bare `GComm`/`GAct` head. There is no congruence lemma for `safeT` under contexts anywhere. (`Interleave.v` has `SW_under_act`/`SW_under_goal`/`SW_under_comm` — the authors clearly know how to do this, they just did not do it for repairs.)

**Concrete fix.** Define one-hole contexts `C[·]` over `Gt` and prove `(forall b W, safeT b G W -> safeT b G' W) -> forall b W, safeT b C[G] W -> safeT b C[G'] W`. That single lemma promotes all four repairs from root to arbitrary position, and it is the same lemma you need for W9(ii).

### W8 — **MAJOR.** The verified kernel decides a *different* goal predicate from the one the theory defines

`Kernel.v:179–186`:

```coq
Definition goal_hit (goal : F) (s : GW) : bool := is_end (fst s) && satf goal (snd s).
Definition goal_reach ... := exists w', reach GW (gsucc hz tbl) (G, w) (REnd Gd, w') /\ satf goal w' = true.
```

`goal_reach` requires reaching **`REnd`** with the goal true, and `gsucc` concatenates `succ0 ++ succ1`, so misselections are **free and unbounded**. The theory's goal-reachability is `reach_haz E Phi b G W` (`Severity.v`, `Definition Futile`/`Benign`), which is (i) **budgeted** and (ii) fires at **any** state where `Φ` holds, `End` or not.

So `goal_reachable_correct` (`Kernel.v:205`) certifies the elaboration's rational guards and derived hazard bits against a predicate the metatheory never uses. `kernel_first_spec` (the hazard half, and hence the `k*` cross-check and the 499/499 differential test) is fine — it is `reach_mu` on the hazard bit, which does match. But `Benign`/`Futile` as computed by `skillc severity --verified` are not the `Benign`/`Futile` of Definition 5, and the paper says nothing about this.

**Concrete fix.** Pick one notion and prove the other agrees under stated conditions. Either (a) change `Futile`/`Benign` in `Severity.v` to end-and-goal reachability and re-derive the ordering results (they should survive: `reach` to `End` is still monotone in the budget), or (b) keep the theory's notion and change `goal_hit` to `satf goal (snd s)` plus a budget component. Then state in §8 which notion the kernel decides. As it stands the paper's strongest evidence sentence — *"this is the strongest evidence we can offer that the tool computes the quantity its own mechanized theory defines"* (l.~870) — is true of `k*` and false of the severity labels.

### W9 — **MAJOR.** "Why is this a type system?" is answered by assertion. The ingredients of a real answer are in the artifact, unnamed

The reviewer's question is anticipated (§6, l.567–578; §9 title) and the answer given is: exactness buys refutation asymmetry, syntax-directedness, and "it is a judgment on `(G,W)` rather than a decision procedure over a graph, and a decision procedure alone does not compose with a typing derivation". That is the right instinct and it is unsupported — the only thing `⊢_b` composes with is `TC_seq`, which is itself a semantic statement about `ends`, and `TC_regular` says the judgment *is* the graph question. A PC member will read §6 and conclude the rules are `reach_haz` with a negation pushed through, because that is what the paper says (l.568) and what `TC_complete` (`Severity.v:394`, by induction on `Gt_size`) does.

Here is what would make it type-theoretic. All five items are cheap relative to their payoff, and three of them are already half-proved.

**(i) Subsumption.** `tolerance_downward_closed` (`Severity.v`) *is* budget subsumption: `b' ≤ b`, `⊢_b G,W` ⟹ `⊢_{b'} G,W`. Present it as an admissible rule

```
        ⊢_b G,W    b' ≤ b
  T-Sub ───────────────────
           ⊢_{b'} G,W
```

and say the budget order is the subsumption order, with larger `b` the stronger type. One display, and the paper suddenly has a subsumption story. Currently it is a monotonicity remark in the last paragraph of §6.

**(ii) A subtyping preorder — this is the big one.** `repair_narrow_sound` is *exactly* internal-choice covariance, i.e. the standard MPST subtyping direction on selection. Define

`G ≤ G'` as the congruence closure (over the contexts of W7) of: branch removal at a choice; and prove `G ≤ G' ⟹ (⊢_b G,W ⟹ ⊢_b G',W)` and `ctypes G s W ⟹ ctypes G' s W`. Then ask the question a reviewer will actually ask and that the paper never asks: **is `k`-tolerance monotone in this preorder?** (It should be — narrowing removes misselectable branches — and the answer would be a one-line corollary of the congruence lemma.) That single subsection converts thm:narrow from an ad-hoc repair lemma into a subtyping result, fixes W7, and gives §9 an answer with content: *a decision procedure has no subtyping; a judgment closed under a protocol preorder does.*

**(iii) Declarative vs algorithmic.** `safeT`'s `ST_Act` premise is `forall W'. E a W W' -> safeT b G W'`, quantified over `World = Var -> nat` (`Severity.v:32`) — an **infinitary, semantic** premise. Calling this "syntax-directed" (abstract; C2, l.269; l.573) is at best a term of art: it is syntax-directed in `G` and oracular in `W`. The genuine algorithmic system is `decide_mu`, and its relation to `⊢_b` runs only through `TC_regular` on the *finite* fragment under the `worlds`/`worlds_closed`/`satb`/`succE`/`hazb` hypotheses of `Mu.v`'s `MuDecide` section. Present the declarative/algorithmic pair explicitly, name the hypotheses under which they coincide, and stop calling the declarative one an algorithm.

**(iv) Minimal budget / principality.** `k*` is a principal-type notion and the paper knows it ("the tolerance degree `k*` is the headline"). It is mechanized **only** in the bit-vector kernel, bounded by `kmax`: `kernel_first_spec` (`Kernel.v:147`) returns the least `k` with a hazard, or `None` if none up to `kmax`. In the abstract setting `k*` appears only in Proposition 4 (l.780), which is a **paper proof**. Prove, under the decidability hypotheses you already assume,

```coq
Theorem minimal_budget : forall G W,
  (forall b, decidable (reach_haz E Haz b G W)) ->
  (forall k, safeT E Haz k G W) \/
  (exists k, safeT E Haz k G W /\ ~ safeT E Haz (S k) G W).
```

and call it the principal-budget theorem. `tolerance_degree_is_a_threshold` is 80% of the proof. This is the single most conspicuous missing theorem for a types audience.

**(v) Inversion and substitution.** No inversion lemmas are stated as lemmas anywhere; `inversion` is invoked ad hoc inside proofs. That is acceptable Coq practice and unacceptable paper practice: an ECOOP reader expects to see the inversion principles for `⊢_b` written out, because they are what a reader reasons with. Substitution exists only for μ-unfolding (`subst_comp`), not for typing — which is fine given there are no term variables, but say so.

### W10 — **MAJOR.** Hypotheses smuggled into Theorem 1 and Theorem 7

- **thm:ordered (l.486)** cites `benign_step_up` and `benign_step_down` as unconditional. In Coq both carry an explicit decidability disjunct as a premise (`Severity.v:319`, `:331`), as does `severity_classes_are_separated` (`:376`). thm:partition (l.509) *does* disclose its hypothesis ("exhaustive whenever the two reachability questions are decidable"); thm:ordered does not, and it is the headline of C3.
- **thm:progress (l.620)** assumes `forall (psi : World -> Prop) (W : World), psi W \/ ~ psi W` (`Bridge.v:139`) — excluded middle over *all* guard predicates. This is disclosed only in a trailing parenthesis, as "guard decidability".
- `severity_monotone_in_budget` (`Severity.v:352`) takes `sev_rank` facts at both budgets as premises, so it does not by itself establish that a residual *has* a class at every budget; that needs exhaustiveness, i.e. the same decidability. The paper's "the rank of a residual is monotone non-decreasing in its budget" presupposes totality of a function that is only a relation.

**Concrete fix.** Introduce a named standing hypothesis in §5 — *Assumption 1 (decidable guards and decidable reachability): for the QF-LIA fragment with finite abstract worlds, `W ⊨ ψ`, `(G,W)↝^H_b` and `(G,W)↝^φ_b` are decidable* — and cite it in thm:ordered, thm:partition and thm:progress. It costs three lines and removes the smell entirely. Do **not** leave it implicit: the paper's selling point is axiom-freeness, and the reason the development is axiom-free is that these are hypotheses; a reader who does not open the `.v` files will read "axiom-free" as "constructive throughout".

### W11 — **MAJOR.** The condition, as a *rule system*, does not exist for recursive protocols

There is no `safeT` for `Gr` in `Mu.v`. `bridge_mu` (`Mu.v:700`) takes `~ reach_mu b G w` — a **semantic** hypothesis — not a typing derivation. `TC_regular` (`Mu.v:887`) relates `safeT` to `reach_mu` only through `emb`, i.e. for the **finite** fragment. So:

- abstract: *"One syntax-directed rule characterizes the condition exactly … The condition … is decidable for regular protocols"* — these are true of two different objects, and the sentence invites the reading that the rule extends to μ-types.
- thm:bridge-mu (l.655) is correctly stated ("a protocol on which no hazard is reachable within budget k"), so the body is honest; the abstract and C2 are not.
- `bridge_finite_via_mu` (`Mu.v:894`) is described as recovering Theorem 6 (l.663). It does not, quite: it uses `Mu.v`'s **coinductive** `ctypes` over `Pr` processes and `Mu.v`'s `hrun`, not `Bridge.v`'s inductive `ctypes` over `Proc`. It recovers the *conclusion* in a different session calculus.

**Concrete fix.** Either define `safeT` coinductively on `Gr` (with the `RMu` rule `⊢_b G[μX.G/X],w ⟹ ⊢_b μX.G,w`) and prove `TC_exact_mu`, restating thm:bridge-mu as a typing statement — this is the right answer and probably not hard given `cands_closed` — or add one sentence to §7 and the abstract: *"for μ-types the condition is stated semantically and decided by `decide_mu`; the rule presentation is a finite-fragment result."*

### W12 — **MAJOR.** Progress is finite-fragment only, and contractiveness is claimed but never formalized

`progress` and `every_label_steps` live in `Bridge.v` over `Gt`/`Proc`. `Mu.v` has **no** progress theorem. That is precisely where progress is interesting and where it can fail: `ctypes` in `Mu.v` is coinductive, and §12 admits `μX.X` types against anything. §12 says "contractiveness is assumed as usual" — `grep -ni contract proof/*.v` returns exactly one hit, a comment in `Bridge.v:268` about budget *contracts*. **Contractiveness is not defined, not assumed, and not used anywhere in the mechanization.** `unfp_det` (`Mu.v:93`) gives determinacy of head-unfolding but does not give termination of unfolding, which is what contractiveness buys.

**Concrete fix.** Define `contractive : Gr -> Prop` (no `RVar`/`RMu`-only cycle before a communication or action), add it as a hypothesis where needed, and prove `progress_mu`. Or restate thm:progress in the text as a finite-fragment result and say plainly that progress for recursive sessions is open.

### W13 — **MAJOR.** §9's answer to "why not a model checker" rests on a one-line corollary plus an unmechanized abstraction

`TC_seq` (`Severity.v:634`) is a genuine and pleasant theorem. `TC_seq_interface` (`Severity.v:668`) — on which §9's whole argument is hung (l.812–832) — is four lines: `apply TC_seq; intros; apply HI; apply Hends`. It assumes the interface `I` is handed to you. The paper then concedes (l.822–828) that the *concrete* interface is exponential and that what makes modularity pay is the **cone-of-influence projection**, asserted sound in one clause: *"sound because dropped atoms cannot affect them"*. That soundness claim is the load-bearing one, it is the difference between 35.8 s and 0.13 s in Table 2, and **it is not mechanized**.

**Concrete fix.** Mechanize it. State cone-of-influence as a relation `W ≈_V W'` (agreement on a variable set `V` closed under the remaining segments' reads) and prove `safeT`-invariance under `≈_V` when `V` covers `supp(Haz) ∪ supp(Φ) ∪ ⋃ pre/eff` of the remainder. `Interleave.v`'s `Strips` section (`supported`, `footprint`, `strips_preserves`, `strips_neutral`) already has 80% of the machinery. Without it, §9 answers "why not a model checker" with a theorem that does no work and an abstraction that is not proved.

### W14 — **MINOR.** `SW_comm_comm`'s product-form side condition is not in the paper

The paper (l.~680) describes the communication/communication swap as "two communications `p→q` and `r→s` between disjoint role pairs, each branch of the first continuing with the second". The Coq relation (`Interleave.v:75`, with `orig_cc`/`new_cc` at `:49`/`:53`) requires the continuation to factor as `K l m` over the **full product** of the two label sets — every `l` branch must contain the identical `r→s` choice with the identical guards, and continuations must depend only on `(l,m)`. That is a real syntactic restriction (it excludes any protocol where the second communication's shape depends on the first's label) and the prose does not convey it. Also note this is a *permutation of the global type*, not a concurrent semantics: `irun` (`Interleave.v:471`) rewrites `G` by `swaps` before each head step. The word "interleaving" oversells it.

**Fix.** State the product form in the theorem statement or in a displayed equation, and say explicitly that thm:bystander is a protocol-rewriting result, not an out-of-order semantics.

### W15 — **MINOR.** Proposition 4 mixes two cost models and has no hardness result

`|World| = 2^{|Pred|}` gives PSPACE for the *succinct* presentation; the mechanized and extracted procedure enumerates `nodes × worlds × {0..k}` **explicitly** (`Regular.v:560` `decide_reachb`, `Kernel.v:83` `all_bits`), so it is exponential *time and space* in `|Pred|`. "Each iteration is linear in the product" (l.790) is therefore exponential and reads as though it were cheap. There is no hardness result, so "in PSPACE" is uninformative — a reviewer wants PSPACE-completeness or nothing. Separately: Prop 4 says the `k*=∞` test is "plain reachability with misselection edges made free", which is cheap — yet the tool never performs it (Table 1 reports "≥5", caption l.919), so the headline number is a lower bound on `k*`, not `k*`.

**Fix.** Split the complexity claim by cost model; state PSPACE-hardness or drop the class; implement the free-misselection reachability test so the tool can report `∞`. The last is a few lines and would materially improve Table 1.

### W16 — **MINOR.** Notation and definitional hygiene

a. The judgment is written `⊢_b G , W` (l.539 ff.). The comma reads as a typo. More importantly, `Γ` and `H` are section parameters in Coq (`Variable E : Ctx`, `Variable Haz`) and are invisible in the paper's judgment form. Write `Γ; H ⊢_b G ⊳ W`, or state once that they are implicit.
b. `↝^φ_b` (macro at l.120, first used l.474) is introduced by the phrase "is budgeted goal reachability" and never given rules. Say `↝^φ_b := ↝^H_b[H := φ]` — one clause — or give the rules.
c. Definition 6 (point of no return, l.519) has a **free `b`**: *"`(G,W)` is a point of no return for `φ` if `¬(G,W)↝^φ_b`"*. Quantified how? As written the definition is ill-formed. (`Severity.v` has no `PNR` definition at all, so the Coq cannot arbitrate.)
d. `\Rec` = `Recoverable` (l.122) is a dead macro from an abandoned four-class design. There are ~25 further dead macros from the withdrawn draft (`\MC`, `\mok`, `\mdr`, `\Taint`, `\Crit`, `\Irr`, `\Att`, `\Rfr`, `\provv`, `\tick`, `\Conf`, `\dev`, `\Eprof`, `\Dmax`, …). Harmless but they are the fingerprints of the predecessor.
e. `reach_haz` is the Coq name used for *goal* reachability too (`Definition Futile := ... ~ reach_haz E Phi b G W`). Rename to `reach_b` or `reachP`.
f. `T-Goal` (l.547) and `CT_Goal` use the same `φ` with different force — see W3.
g. §10's four repair theorems (l.1228–1266) are forward-referenced from §8 Finding 4 (l.~1040) and from the abstract. Move §10 before §8 or accept the forward reference explicitly.

### W17 — **MINOR.** The result count is inflated by the audit of a paper that no longer exists

"93 results" (l.191, README) includes the **14** `DeviationLayer.v`/`check_dev.v`/`check_co.v` results, which are refutations of the *withdrawn* predecessor (`AUDIT.md`). The present theory's mechanization is 79. The `\supplement` field and the draftnote should say "79 results for the theory of this paper, plus 14 for the audit reported in §11". Also the draftnote claims "everything in §§5–9 is mechanized"; per W4, Definition 2 in §4 is not, and per W11 the *rule* of §6 is not lifted to §7's μ-types.

### W18 — **MINOR (but read it).** What is trivial is billed as deep; what is deep is buried

Trivial, currently in theorem environments or contribution bullets:
- `severity_disjoint` (`Severity.v:260`) is `repeat split; intros [H1 H2]; contradiction` — the classes are disjoint **by construction** (`Cat := R_H`, `Fut := ¬R_H ∧ ¬R_Φ`, `Ben := ¬R_H ∧ R_Φ`). It is half of numbered Theorem 2.
- `severity_exhaustive` is `tauto` after two decidability disjuncts.
- `budget_distributes` — see W5.
- `TC_seq_interface` — see W13.
- `catastrophic_upward`, `futile_downward`, `benign_no_regress` are each two lines off `reach_mono_budget`.

Deep, currently four lines of prose (thm:cands, l.754):
- `subst_comp` (`Mu.v:302`), `unfold_close` (`:344`), the `good`/`okst` invariant (`:386–528`), `okst_step` (`:463`), `cands_closed` (`:529`). This is the only part of the artifact where a reader would learn something they could not have reconstructed, and it is the part that makes decidability for μ-types a *theorem* rather than an assumption. Give it a subsection, state the invariant, and show why the naive "subterms of `G₀`" set is not closed and the closure-under-enclosing-binders set is.

Rebalancing these two lists would improve the paper's reception more than any new theorem.

---

## (d) The single change that would most raise the score

**Mechanize non-vacuity, and run it against your own repairs.**

Concretely: define the canonical session `erase(G)`, prove `ctypes E (erase G) W` for an explicit well-formedness predicate, add it to `check_bridge.v` and `check_mu.v`, and then apply it to the guard-repaired and reorder-repaired protocols of §10 and to the protocols of Table 1.

I single this out because it is one change that discharges the paper's three worst problems at once. It forces W1 into the open (you will discover that `CT_Act`'s enabledness premise makes the repaired protocol unconformable, and you will then fix `CT_Act` or the repair, either of which is a better paper). It forces W3 into the open (you will discover that `CT_Goal` makes goal-marked protocols with losable goals unconformable). And it retires W2 by construction. It costs perhaps 200 lines of Coq and it converts the paper's most exposed flank — *"the payoff theorem may be vacuous exactly where it is advertised"* — into a stated theorem.

It is also the change the paper's own §11 obliges you to make. You withdrew a draft because a mechanized audit found its type system vacuous. Ship the audit.

*Second-best, if you want a type-theoretic contribution rather than a repair:* W9(ii)+(iv) — the branch-narrowing subtyping preorder with `k`-tolerance monotone in it, plus the principal-budget theorem. Those two together are what would let you answer "why is this a type system" with a theorem instead of a paragraph.

---

### Minor factual notes for the authors

- `Bridge.v` gained `progress`/`every_label_steps` and `main.tex` gained thm:progress at commit `61b878e`, after the `main.pdf` in the directory was built at 20:26 on 2026-09-02. I reviewed the source, not the stale PDF. thm:progress is a real improvement and directly addresses the first question I would otherwise have asked — but see W1 and W12 before you rely on it.
- `bridge_run` (`Bridge.v:236`) concludes `~ Haz W'` for the run's **endpoint**. thm:bridge (l.613) says "along every run of total cost at most `k`, **no configuration** is a hazard state". True by prefix-closure of `hrun`, but not mechanized. One lemma (`hrun_prefix`) or a weaker sentence. Same for `bridge_mu` and `bridge_interleaved`.
- `bibitem{morak-kr25}`, `{lebrun-esop23}`, `{agentltl}`, `{pact}`, `{etas}` all still carry `[to verify]`. `{morak-kr25}` has no authors at all.
- The `DO-NOT-SUBMIT-WHILE-THIS-LINE-EXISTS` marker, the `\draftnote` boxes and the `anonymous`-with-`\thanks`-naming-internal-file-paths title (l.140–142, which deanonymizes) are all still present.
