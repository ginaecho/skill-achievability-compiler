# ECOOP review — R4 (theory and mechanization, SECOND ROUND)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that Choose Wrongly*
**Reviewer expertise:** behavioural types, MPST, concurrency, mechanized metatheory.
**Scope:** `main.tex` (current, commit `bb9c384`) and `proof/{Severity,Bridge,Mu,Regular,Interleave,Repairs,Kernel}.v`. I read the `.v` files in full, not just the theorem statements, and I **re-proved five claims in Coq against the shipped development** to check the paper's prose. Those five probe files compile with `coqc -Q proof "" probe.v` against the shipped `.vo`s and every one prints `Closed under the global context`. Their statements are quoted verbatim below; the authors can paste them into `proof/` and reproduce.

---

## (a) PART 1 — verification of the round-1 revisions

| # | Round-1 issue | Verdict | Evidence |
|---|---|---|---|
| (a) | Guard repair makes the repaired protocol uninhabited in exactly the worlds it addresses (`validates` ⇒ capability disabled ⇒ `CT_Act` unsatisfiable) | **PARTIALLY FIXED, and the fix carries a claim that is FALSE** | New model `validates_ab` (`Repairs.v:46`) + `validates_ab_enabled` (`:51`), `halted` (`:44`), `reach_halted` (`:61`), `safeT_halted` (`:80`), `guard_abort_is_futile` (`:89`), disclosed in `main.tex:1364` thm:guardabort. But: (i) the aborting model **does not restore conformance** — probe P1 below; (ii) `main.tex:1376` "every claim made with it also holds of the aborting model" is **refuted** — probe P2; (iii) the reorder half of the same defect was not touched at all — probe P5; (iv) `halted` is never instantiated anywhere in the development and is **unsatisfiable in the paper's own capability models** — probe P4. |
| (b) | No inhabitation / non-vacuity result | **FIXED (narrowly), with one unsupported gloss** | `Gbad_inhabited` (`Bridge.v:447`), `Ggood_inhabited` (`:420`), `Gbad_bridge_nonvacuous` (`:484`) all exist, are `forall W`, and are axiom-free. thm:inhabited (`main.tex:679`) is accurate except "and **can take the misselected branch**" — no Coq lemma exhibits a misselecting `hstep` from `MBad`; `every_label_steps` is never instantiated on it. Scope is honestly disclosed (`main.tex:687–694`). |
| (c) | `CT_Goal` requires `phi W` on every branch ⇒ goal-marked protocols with goal-losing branches are untypable | **NOT FIXED** | A prose caveat was added (`main.tex:694–701`) but the sentence "The marker therefore belongs where **the condition** guarantees it" is incoherent: the condition is `safeT`, and `ST_Goal` (`Severity.v:116`) **drops `phi` entirely** — `safeT` never guarantees `phi`, so there is no placement satisfying the stated rule. No `wf` predicate, no Coq lemma, no tool check. The three sub-symptoms R1 named all survive: `✓φ` is inert in `⊢_b`; `EN_goal` (`Severity.v:623`) and `RH_goal` (`:98`) also ignore it; and the syntactic `φ` is still formally unrelated to `Section Severity`'s `Variable Phi` (`Severity.v:248–252`) while the paper writes both as `φ`. |
| (d) | Decidability hypotheses smuggled into parentheses | **PARTIALLY FIXED** | Assumption 1 now exists (`main.tex:497`, ass:dec) and thm:progress cites it. But thm:ordered (`:505`) still cites `benign_step_up` (`Severity.v:319`) / `benign_step_down` (`:331`) / `severity_classes_are_separated` (`:385`) with no local flag, and — the one that matters — thm:exact's clause "**hence** a branch is \Cat{} iff its residual fails the condition" (`main.tex:580–584`) is a classical step (`~~reach ⇒ reach`) whose Coq witness `untypable_implies_catastrophe` (`Severity.v:410`) takes a decidability premise and **is not cited there at all**. |
| (e) | No progress theorem | **FIXED; statement is faithful** | `progress` (`Bridge.v:139`) and `every_label_steps` (`:165`) match thm:progress (`main.tex:703`) exactly, including the `Hdec` premise, which the theorem flags. The "every label the sender may pick" gloss is correct because `CT_Comm`'s `Hl1`/`Hl2` (`Bridge.v:64–65`) force label-set equality. (See W6 below on what this theorem is worth.) |
| (f) | Environment-controlled choice unmechanized but used in the benchmark | **FIXED** | `main.tex:463–467` now states it inside def:budget: "the mechanization covers only participant-controlled choice, so no theorem in this paper is stated for it", and `main.tex:951` excludes it from the verified-kernel fragment. Confirmed: `grep -i "environment\|demonic\|GEnv" proof/*.v` returns nothing. Remaining gap is minor and noted as W10. |

### The probes

**P1 — the aborting model does not restore inhabitation; it moves the hole one node down.**
```coq
Theorem abort_still_uninhabited :
  forall (E : Ctx) a psi ab p q W s a' G',
    validates_ab E a psi ab -> ~ psi W -> halted E (ab W) ->
    ~ ctypes E (GAct a p (GAct a' q G')) s W.
```
`Closed under the global context`. Read it: `validates_ab` makes the *validation* fire, discharging `CT_Act`'s `exists W'` at the validation node — which is all `validates_ab_enabled` proves. But the very hypothesis that makes the branch futile, `halted (ab W)`, makes `CT_Act`'s `exists W'` **unsatisfiable at the next node**. The guard repair guards a branch whose head is an irreversible *action*; that is the entire point of the repair. So in exactly the worlds the repair addresses, the repaired protocol still has no conforming session whenever the guarded residual begins with an action. thm:guardabort's "so the repaired protocol still has conforming sessions" (`main.tex:1367`) is an inference the Coq does not license and that P1 refutes for the intended shape. This is the same defect R1 reported, relocated by one constructor.

**P2 — `main.tex:1376` is false as written.**
```coq
Theorem rhs_holds : safeT E2 Haz0 1 Narrowed W0 /\ (psi2 W0 -> safeT E2 Haz0 1 Gl2 W0).
Theorem lhs_fails : ~ safeT E2 Haz0 1 Guarded W0.
```
Both `Closed under the global context`. `E2` is a validation-with-abort satisfying `validates_ab E2 3 psi2 ab2` where `ab2 W = wupd W aborted 1` — an abort world that *marks* a flag but is not `halted`. Under it the right-hand side of `repair_guard_exact` (`Repairs.v:137`) holds and the left-hand side fails: the guarded protocol is untypable at budget 1 while the narrowed one is safe. So "every claim made with [the blocking model] also holds of the aborting model, whose misselected branch is \Fut{} where the blocking one is empty" is not a scope remark, it is a wrong theorem. What is true is the much weaker `guard_abort_is_futile`, which carries three extra hypotheses (`halted (ab W)`, `~ Haz (ab W)`, `~ Phi (ab W)`) that the paper's sentence silently drops. `repair_guard_sound` (`:116`) and `repair_guard_exact` (`:137`) are **not** re-proved for `validates_ab`; there is no `repair_guard_sound_ab` in the file.

**P4 — `halted` is unsatisfiable in the development's own capability models.**
```coq
Theorem E0_has_no_halted_world : forall W, ~ halted E0 W.
Theorem E1_has_no_halted_world : forall W, ~ halted E1 W.
```
Both `Closed under the global context`. `grep -rn halted proof/*.v` shows `halted` occurs only inside `Repairs.v` and is never instantiated. So thm:guardabort is a theorem whose hypotheses are **never shown satisfiable anywhere in the artifact**, in a paper whose §11 (`main.tex:1512`) says "it is why this paper checks its own theorems for vacuity (Theorem 15, Theorem 22)". Theorem 22 *is* the unchecked one. That is not a nitpick; it is the paper's own stated methodology applied to the paper and failing.

**P5 — the reorder repair was not addressed at all.**
```coq
Theorem reorder_repair_unconformable :
  forall (E : Ctx) chk psi q irr p G W s,
    validates E chk psi -> ~ psi W -> ~ ctypes E (GAct chk q (GAct irr p G)) s W.
```
`Closed under the global context`. `repair_reorder_pnr` (`Repairs.v:241`) still uses the **blocking** `validates`, and its headline conclusion — "the reordered protocol is typable at every budget" — is obtained in `reorder_reordered_exact` (`:221`) by discharging `psi W -> ...` vacuously from `~ psi W`. The reordered protocol is typable there *because `chk` cannot fire*, and by P5 no session conforms to it there. thm:reorder (`main.tex:1386`) states this as the repair's headline with no caveat, and §10's "The blocking model is retained below because the exact characterization is easier to read on it" is doing double duty as an excuse for a defect that was only ever half-fixed. R1's W1 named guard *and* reorder; one was answered with a new definition, the other was not answered at all.

---

## (b) Updated score

**Score: C — weak reject. Confidence 4/5. Unchanged from R1's C, but at the top of the band rather than the bottom.**

Genuinely better: (b), (e), (f) are fixed; W5 (budgets-distribute overclaim) is fixed with an exactly right sentence (`main.tex:733–740`); T-Sub and T-Narrow are now *displayed as admissible rules* (`main.tex:615–632`), which is the round-1 request; the cone-of-influence disclosure (`main.tex:915–917`) and the interface/exit-set honesty in Finding 3 (`main.tex:1096–1103`) are exemplary; thm:narrow now discloses the root-only limitation (`main.tex:1349`); the principal-`k` gap is named as future work rather than papered over.

It stays at C for one reason and one reason only. **The revision introduced a false claim into the very paragraph that repairs the round-1 blocking defect** (P2), while leaving the other half of that defect untouched (P5) and the fix's hypotheses uninstantiable (P4). R1 said "W1–W3 plus one of W9's sub-items would move me to B". W2 is done. W3 (issue (c)) is not. W1 is not — it is now half-answered with a wrong sentence, which is worse than the honest disclosure R1 offered as option (c). A PC member who runs P2 will not read the rest of §10 charitably.

Flipping to **B** requires exactly three things, all cheap: fix or delete `main.tex:1376`; give the guard repair a soundness theorem for `validates_ab` under stated abort-world conditions and an inhabitation witness for it; and either make `CT_Goal` premise-free or delete `✓φ` from the language. That is a week, not a rewrite.

---

## (c) Remaining weaknesses

### W1 — **BLOCKING.** §10's guard/reorder paragraph contains a false claim and an uninstantiable theorem
*Severity: blocking.* Evidence: probes P1, P2, P4, P5 above; `Repairs.v:26,44,46,89,116,137,241`; `main.tex:1364–1400`.

Three separate defects wearing one patch:
1. `main.tex:1376` ("every claim made with it also holds of the aborting model") is refuted by P2.
2. thm:guardabort's "so the repaired protocol still has conforming sessions" does not follow from `validates_ab_enabled` and is false for the repair's intended shape (P1).
3. thm:reorder still rests on the blocking model (P5).

**Concrete fix.** (i) Delete `main.tex:1376` and replace it with the actual scope: *the exact characterization holds of the blocking model; of the aborting model we prove futility only under `halted(ab W) ∧ ¬Haz(ab W) ∧ ¬Φ(ab W)`.* (ii) Prove `repair_guard_sound_ab : validates_ab a psi ab -> halted (ab W) -> ~ Haz (ab W) -> safeT b (GComm p q brs) W -> (psi W -> safeT b Gl W) -> safeT b (GComm p q ((l,psi,GAct a p Gl)::brs)) W` — it is ten lines from `safeT_halted`. (iii) The real fix for P1: model the validation as R1's option (b), a two-branch construct `chk?{ok.G ; abort.R}` with `R` a *communication or `End`*, not an action, so `CT_Act`'s enabledness premise is never reached in the abort world; then exhibit a conforming session for the guard-repaired booking protocol and put it in `check_repairs.v`. (iv) Either restate thm:reorder with the same disclosure or reprove `repair_reorder_pnr` for `validates_ab`. (v) Add a concrete `E` with a halted world (one extra capability whose precondition is `¬aborted`, or simply a `Ctx` that is empty at `ab W`) and instantiate thm:guardabort on it. Right now no reader can tell whether the aborting model is inhabitable at all.

### W2 — **BLOCKING.** `✓φ` is dead syntax with a live premise, and the "scope condition" is not a condition
*Severity: blocking (as W3 was).* `Severity.v:98` (`RH_goal`), `:116` (`ST_Goal`), `:623` (`EN_goal`), `Bridge.v:50` (`CT_Goal`), `Mu.v` (`RGoal`/`M_goal`), `Interleave.v` (`SW_goal`) — the marker is threaded through every relation in the development and is *inert in all of them except `CT_Goal`*, where it is a hard premise. The paper's new sentence (`main.tex:694–701`) says the marker "belongs where the condition guarantees it"; the condition guarantees nothing about `φ`, so the rule cannot be followed. The escape clause ("the benchmark carries the goal as a pack-level condition and uses no inline markers") means the construct is exercised by nothing and is carried purely for decoration.

Worse, the two `φ`s are still different objects. `Definition Futile`/`Benign` (`Severity.v:250,252`) are parameterized by `Variable Phi`, which no rule ever connects to any `GGoal phi`. §5 opens "Let `φ` be the goal" one page after §3 introduced `✓φ` as the goal marker. There is no definition, no lemma, and no sentence relating them.

**Concrete fix.** Pick one and say which. (a) Make `CT_Goal` premise-free, add a separate *marker-satisfaction* obligation stated over runs, and prove it is exactly what \Ben{} guarantees and \Fut{} forfeits — this is the interesting option and it would finally give `✓φ` typing content and connect it to the trichotomy. (b) Delete `✓φ` from `Gt`, `Gr`, all four relations and the paper, and keep the goal as the `Phi` parameter only. (b) costs an afternoon and loses nothing the paper currently uses. Either way, add one displayed definition relating the syntactic marker to the semantic `Φ`, or state in one sentence that they are independent inputs.

### W3 — **MAJOR.** The μ-layer has no judgment at all, and the abstract does not say so
*Severity: major.* There is no `safeT` for `Gr`. `bridge_mu` (`Mu.v:700`) takes `~ reach_mu b G w` — a semantic non-reachability hypothesis (`Mu.v:381`), i.e. a model-check result. `TC_regular` (`Mu.v:887`) relates `safeT` to `reach_mu` only through `emb`, whose image never contains `RMu`. `TC_seq`/`TC_seq_interface` (`Severity.v:634,668`) and `gseq` are likewise `Gt`-only: **modular composition does not exist for recursive protocols either**, and §9 never says so.

The body is honest — thm:bridge-mu (`main.tex:741`) correctly says "a protocol on which no hazard is reachable within budget `k`". The abstract is not: *"One syntax-directed rule characterizes the condition exactly … and the guarantee survives recursion … The condition composes against an interface … and is decidable for regular protocols"* (`main.tex:174–180`) is four claims about three different objects in one sentence. R1's W11 asked for either a coinductive `safeT` on `Gr` or one disclosing sentence. **Neither was added.** `grep` confirms no disclosure exists.

Related and also unfixed (R1 W12): `grep -rn contractiv proof/*.v` returns **zero hits**, yet `main.tex:1529` says "contractiveness is assumed as usual". It is not assumed anywhere in the mechanization, and `unfp_det` (`Mu.v:93`) gives determinacy of head-unfolding, not termination of it. There is no `progress` for `Mu.v`.

**Concrete fix.** Define `safeT` coinductively on `Gr` with `ST_Mu : safeT b (unfold_mu G) w -> safeT b (RMu G) w` and prove `TC_exact_mu` by `reach_in_cands` (`Mu.v:538`) — you already have the finiteness argument that makes this work. If you will not, add one sentence to the abstract and to §12: *for μ-types the condition is stated semantically and decided by `decide_mu`; the rule presentation, the exactness theorem and modular composition are finite-fragment results.* And define `contractive` or delete the claim.

### W4 — **MAJOR.** T-Narrow is presented as internal-choice covariance, but conformance is not closed under it
*Severity: major.* `main.tex:626–628`: "T-Narrow is covariance of internal choice, the direction session subtyping already has". A reader trained on session subtyping will infer that a program well-typed against the wide protocol is well-typed against the narrow one. It is not:
```coq
Theorem narrowing_breaks_conformance : forall W, ~ ctypes E0 Ggood MBad W.
```
`Closed under the global context` (probe P3). `CT_Comm`'s `Hl2` (`Bridge.v:65`) forces the sender's offer set to be *exactly* the protocol's label set, so narrowing the protocol invalidates the session. `MGood ≠ MBad` in the development for precisely this reason. So `⊢_b` is closed under narrowing and `G ⊢ (M;W)` is not, and the paper's subtyping analogy holds only for the half that is not about programs. §10 is operationally honest ("remove the branch, so the gate refuses it" — a *runtime* mechanism), but §6 sells it as a typing property.

This is also why the round-1 request for a subtyping preorder was not really answered. "We do not develop a general subtyping preorder: with one index and one direction there is nothing yet to develop" (`main.tex:628–631`) mistakes the request. The preorder R1 asked for is over **protocols** (the congruence closure of branch removal), not over the budget index, and the question it makes askable — *is `k`-tolerance monotone in that preorder, and is `ctypes` closed under it?* — has a non-trivial answer, namely yes for `⊢_b` and **no** for `ctypes`. That asymmetry is a genuine result and the paper currently has it backwards.

**Concrete fix.** Two sentences plus one lemma. State that `⊢_b` is closed under narrowing and `ctypes` is not, with `Bridge.v:65` as the reason, and say that narrowing is therefore a joint protocol/implementation repair. Then define one-hole contexts `C[·]` over `Gt` and prove the congruence lemma `(forall b W, safeT b G W -> safeT b G' W) -> forall b W, safeT b C[G] W -> safeT b C[G'] W`. `Interleave.v:78–84` already has `SW_under_act`/`SW_under_goal`/`SW_under_comm` doing exactly this shape for swaps — you wrote the lemma, you just did not point it at repairs. That single lemma fixes W5 below and turns thm:narrow into a preorder result.

### W5 — **MAJOR.** Repairs are proved at the root; the tool applies them at nested paths, and only one of the four discloses this
*Severity: major.* thm:narrow now discloses it (`main.tex:1349–1352`, "which needs a congruence lemma for `⊢_b` under contexts that we have not proved") — good. thm:guard, thm:reorder and thm:compensate (`main.tex:1378,1386,1399`) do not, and they are equally root-only: `repair_guard_sound` (`Repairs.v:116`) is stated for a bare `GComm` head, `repair_reorder_sound` (`:169`) for a bare `GAct` head, `repair_compensate_sound` (`:260`) for `gseq Gl R` at the top. The tool's own §2 output narrows at `/choice@ops#0/skip_backup/choice@ops#1`. So three of the four repair theorems are cited in support of tool behaviour they do not cover, silently.

**Concrete fix.** The congruence lemma of W4 covers all four at once. Until it exists, extend thm:narrow's disclosure sentence to the other three theorems.

### W6 — **MAJOR.** \Ben{} is angelic, \Cat{} is demonic, and the paper reads \Ben{} as a guarantee
*Severity: major.* `Catastrophic b G W := reach_haz E Haz b G W` and `Benign b G W := ¬reach_haz E Haz b G W ∧ reach_haz E Phi b G W` (`Severity.v:248–252`) use the **same** inductive relation for both. `RH_comm_ok`/`RH_comm_dev`/`RH_act` are existential over branches and over successors. So:
- \Cat{} = *there exists* an adversarial continuation within budget `b` reaching harm — correct, demonic, what you want.
- \Ben{} = *there exists* a cooperative continuation within budget `b` reaching the goal — angelic.

The two quantifiers run over the *same* agent's *same* remaining choices, and the paper never says so. `main.tex:231` glosses \Ben{} as "a detour; the goal is still reachable", and fig:idea draws it as an outcome. It is not an outcome; it is a possibility, quantified over the future choices of the exact participant the paper's premise says you cannot rely on. Nothing in the development says a \Ben{} residual reaches the goal under any strategy, and there is no notion of strategy anywhere. The ordering theorems (`severity_monotone_in_budget`, `benign_step_up`) are all about this mixed pair and therefore inherit the mix without exposing it.

This matters for the evaluation too: Finding 4's "\Cat{} verdicts name branches real agents take" is the demonic half and is sound; any reading of \Ben{} as "the agent will still succeed" is not supported.

**Concrete fix.** Two paragraphs, no new proofs. State the quantifier structure explicitly in def:sev: *\Cat{} is `∃` over deviations (worst case), \Ben{} is `∃` over continuations (best case); a residual is \Ben{} when it is safe against every affordable deviation and the goal survives at least one affordable continuation.* Then either rename \Ben{} to something possibility-flavoured (*recoverable*) or add the demonic variant (`∀` strategies within budget reach `Φ`) as an explicitly-not-proved strengthening. Any reviewer with a games background will ask this in the first ten minutes.

### W7 — **MAJOR.** The verified kernel decides a different goal predicate from the one the theory defines; unchanged from round 1 and now load-bearing for two more claims
*Severity: major.* Unfixed and undisclosed. `Kernel.v:184`:
```coq
Definition goal_reach hz tbl goal G w :=
  exists w', reach GW (gsucc hz tbl) (G, w) (REnd Gd, w') /\ satf goal w' = true.
```
with `gsucc := succ0 ++ succ1` (`Kernel.v:176`). Against the theory's `reach_haz E Phi b G W` (`Severity.v:250,252`) this differs on **two** axes: `goal_reach` is unbudgeted (misselection edges are free and unbounded) and requires termination at `REnd`, while `reach_haz E Phi b` is budgeted and fires at *any* state satisfying `Φ`. They are incomparable, and no lemma relates them.

This is not an isolated definitional wart, because `goal_reach` is what `elab` (`Kernel.v:252`) uses to compute **both** the rational-choice default guards (`Kernel.v:274`) and the derived hazard bits `a_haz` (`Kernel.v:259–261`). So the kernel's *entire semantics* — what counts as a misselection, and what counts as a hazard — is fixed by an unverified elaboration using a goal notion the metatheory never defines, and `kernel_correct`/`kernel_first_spec` verify only the graph search *downstream* of that. The paper says the elaboration is trusted (`main.tex:947–949`, `:1533`), which is honest about the *code* and silent about the *predicate*.

Consequence for the paper's strongest evidence sentence, `main.tex:970–974` — "the strongest evidence we can offer that the tool computes the quantity its own mechanized theory defines". That is true of `k*` (both sides use the hazard bit through `reach_mu`) and **false of the severity labels** and of the rational guards, which is what the 499/499 differential test does *not* discriminate: two thirds of sampled protocols have no reachable hazard at all, and both implementations derive their guards from the same non-theory notion.

**Concrete fix.** State in §8 which notion the kernel decides, in one sentence, and either (a) redefine `Futile`/`Benign` in `Severity.v` as end-and-goal reachability and re-derive the four ordering results (they survive — `reach` to `End` is still budget-monotone), or (b) change `goal_hit` to `satf goal (snd s)` and add the budget component to `gsucc`'s product. (b) is smaller. Do not leave the paper claiming the tool computes the theory's quantity when for two of the three severity classes it computes something else.

### W8 — **MAJOR.** The cone-of-influence projection is asserted, and it carries the entire quantitative modularity claim
*Severity: major.* Disclosed (`main.tex:915–917`: "The interface theorem is mechanized; the projection's soundness is a paper argument, and the speedup rests on it") — credit for the honesty, but the disclosure does not make the claim safe, because the "paper argument" is one subordinate clause: "sound because dropped atoms cannot affect them" (`main.tex:911`). There is no definition of the cone, no statement of the soundness lemma, and no proof — not in Coq and not in the paper.

What rests on it: Table 2's entire projected column, i.e. 48 queries and 2 interface points at `n=6` against 566 and 1149 (`main.tex:1074–1088`); the "linear where whole-system analysis is exponential" sentence (`main.tex:913–915`); and therefore §9's answer to the paper's own title question. `TC_seq_interface` (`Severity.v:668`) is four lines and assumes `I` is handed to you; the whole content is in *which* `I`, and that is the unproved part.

**Concrete fix.** Mechanize it — it is one lemma and you have the machinery. Define `W ≈_V W'` (agreement on a variable set `V`), require `V ⊇ supp(Haz) ∪ supp(Φ) ∪ ⋃ {supp(pre_a) ∪ eff_a : a in the remainder}`, and prove `W ≈_V W' -> safeT b G W -> safeT b G W'` for `G` whose footprint is inside `V`. `Interleave.v`'s STRIPS section (`supported`, `footprint`, `strips_preserves`, `strips_neutral`) is 80% of it and is already axiom-free. Without this, §9 answers "why not a model checker" with a four-line corollary plus an unproved abstraction, and the reply "the projection is standard" is exactly the reply a model-checking paper would give.

### W9 — **MODERATE.** No principal/minimal-budget theorem, and the reason given for not having one is wrong
*Severity: moderate.* `main.tex:630–632`: "a minimal-budget (principal-`k`) result is future work — `k*` is computed, not derived." `k*` is the paper's headline quantity (abstract, C3, every table column). A types audience reads "the tolerance degree is the type" and expects a principality statement. What is missing is small:
```coq
Theorem minimal_budget : forall G W,
  (forall b, reach_haz E Haz b G W \/ ~ reach_haz E Haz b G W) ->
  (forall k, safeT E Haz k G W) \/
  (exists k, safeT E Haz k G W /\ ~ safeT E Haz (S k) G W).
```
`tolerance_degree_is_a_threshold` (`Severity.v`) plus `catastrophic_upward` is most of the proof, under the decidability you already assume in Assumption 1. Calling it "computed, not derived" is a category error: `kernel_first_spec` (`Kernel.v:147`) computes it *in the bit-vector fragment bounded by `kmax`*; the abstract statement that it exists at all is unproved. That is the difference between an algorithm and a principality theorem, and it is the single most conspicuous absence for this venue.

**Concrete fix.** Prove the display above, call it the principal-budget theorem, and cite it in prop:degree. Ten lines.

### W10 — **MINOR.** Residual overclaims
*Severity: minor, but each is checkable and a hostile PC member will check them.*
1. `main.tex:180`, abstract: "the tool's decision on the boolean fragment **is** a kernel extracted from that proof." §8 says the opposite about the default path (`main.tex:934–937`: "it is not extracted from the proof"); the kernel is reachable only via `--verified`, on a fragment excluding environment choice and arithmetic, and downstream of the trusted elaboration of W7. Weaken to "can be cross-checked against a kernel extracted from that proof".
2. thm:bridge (`main.tex:673`): "along every run of total cost at most `k`, **no configuration** is a hazard state". `bridge_run` (`Bridge.v:236`) concludes `~ Haz W'` for the run's **endpoint**. True by prefix-closure of `hrun`, still not mechanized (`grep -rn prefix proof/*.v` finds only a comment at `Bridge.v:233`). One five-line `hrun_prefix` lemma, or weaken the sentence. Same for `bridge_mu` and `bridge_interleaved`. R1 flagged this; nothing changed.
3. thm:inhabited: "and can take the misselected branch" — unproved (see PART 1(b)). Instantiate `every_label_steps` on `Gbad`/`MBad`; it is three lines given `Gbad_inhabited`.
4. The comm/comm swap display (`main.tex:768–770`) annotates the side condition as "(no condition)". `SW_comm_comm` (`Interleave.v:75–77`) requires the continuation to factor as `K l m` over the **full product** of the two label sets — every `ℓ`-branch must contain the identical `r→s` choice with identical guards. The display hides this by writing singleton branch sets. State the product form or drop "(no condition)".
5. Non-vacuity is exhibited only for two hand-built protocols with no goal markers, no recursion, no validations, and none of the 17 benchmark protocols. That is fine as a first witness and should be said, rather than left for a reviewer to notice that `Gbad`/`Ggood` are the only inhabited objects in the artifact.
6. Progress is a one-step theorem in the **head-move** semantics, in which exactly one role is ever enabled. "A misselection is therefore never … a deadlock" (`main.tex:711`) is true but nearly contentless: there is no interleaving in which a deadlock could arise. `Interleave.v` permutes the *global type* before each head step (`irun`), which is a protocol-rewriting result, not a concurrent semantics. Say what progress does and does not buy.

---

## (d) The single highest-value remaining change

**Make the guard repair a repair: give it a construct that is live, a soundness theorem for the aborting model, and a conforming session — and delete `main.tex:1376`.**

Concretely: replace the `GAct chk` encoding of a validation with an explicit two-branch node `chk?{ok[ψ].G ; abort[¬ψ].R}` where `R` is `End` or a communication; prove `repair_guard_sound_ab` and `repair_guard_exact_ab` on it; exhibit `ctypes` for the guard-repaired booking protocol at a world where `ψ` fails; and add all three to `check_repairs.v`. Then do the same for `repair_reorder_pnr`.

I single this out over W7 and W8, which are individually larger, for the same reason R1 singled out non-vacuity. This is the one change that discharges the paper's most exposed flank *and* the one the paper's own §11 obliges it to make. §11 says the predecessor was withdrawn because a mechanized audit found a premise that could not be satisfied, and says the present paper therefore checks its own theorems for vacuity. Right now, the theorem §11 cites as evidence of that practice (thm:guardabort) has hypotheses that are false in every capability model the artifact contains (P4), does not establish what its own paragraph says it establishes (P1), and sits under a sentence that is refutable in fifteen lines of Coq (P2). A reviewer who runs those probes will conclude that the vacuity check §11 boasts about was not run on the revision. Run it, and this becomes a B.

*Second-best, if the authors want a type-theoretic contribution instead of a repair:* W4's congruence lemma plus W9's `minimal_budget`. Together they turn thm:narrow into a preorder result, promote all four repairs from root to arbitrary position, and give `k*` the principality statement the abstract already implies it has — and they answer "why is this a type system" with two theorems rather than a paragraph.

---

### Reproduction

The five probes are in the session scratchpad and compile against the shipped `.vo` files with:
```
cd proof && coqc -Q . "" probe.v      # Coq 8.18.0, stdlib only
```
P1 `abort_still_uninhabited`, P2 `rhs_holds`/`lhs_fails`, P3 `narrowing_breaks_conformance`, P4 `E0_has_no_halted_world`/`E1_has_no_halted_world`, P5 `reorder_repair_unconformable`. All print `Closed under the global context`. No file in `proof/` or `main.tex` was modified.
