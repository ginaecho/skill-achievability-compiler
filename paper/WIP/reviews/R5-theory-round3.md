# ECOOP review — R5 (theory and mechanization, THIRD ROUND)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that Choose Wrongly*

**Reviewer expertise:** behavioural types, MPST, concurrency, mechanized metatheory.

**Snapshot reviewed.** `main.tex` and `proof/` as of commit `2acae63` ("Mechanise the cone of
influence…") plus the shipped `.vo` files built at 22:19. The tree moved five times *during*
this review (`813e15c` → … → `32ddf72` → `8abfa04`); I re-checked every finding against the tree
at `8abfa04` and all of them survive verbatim. **Line numbers below are those of the reviewed
snapshot and have already drifted by about ten lines in `main.tex`; the quoted sentence, not the
number, is the anchor.** Two process notes: (i) mid-review,
`proof/Bridge.v` carried an **uncommitted, non-compiling** addition (a general two-role
inhabitation construction `canon`/`sess_of`/`two_role`; `coqc` failed at `Bridge.v:765`,
"The variable Gl0 was not found"). It has since been committed as `8abfa04`, which **does** build
(`coqc -Q . "" Bridge.v`, exit 0), and all six probes below still compile against the rebuilt
development. (ii) commit `32ddf72` added a vacuity paragraph to the introduction
(`main.tex:315–322`) whose last clause I contest below.

**Method.** I read `Repairs.v`, `Abort.v`, `Bridge.v`, `Severity.v`, `Mu.v` and `Kernel.v` in
full, `Check`ed the elaborated statement of every result the round-3 rebuttal names (so that
Section-discharged hypotheses are visible), and wrote **six new probe files** against the
shipped development. All six compile with `coqc -Q proof "" probe.v` and all thirteen results
print `Closed under the global context`. Statements are quoted verbatim below. No file in
`proof/` or `main.tex` was modified.

---

## (a) PART 1 — verification of the round-2 revisions

| # | R4 issue | Verdict | Evidence |
|---|---|---|---|
| **W1** | Guard/reorder repair vacuity; false sentence at old `main.tex:1376`; `halted` uninstantiable | **FIXED as an inhabitation problem; REPLACED by a modelling problem** | The false sentence is gone. `validates_ab` is now stated at a world (`Repairs.v:50`), `halted` is demoted to a discussed dead end, `idle`/`inert` (`:79,:81`) take over, and `repair_guard_sound_ab` (`:210`), `repair_guard_exact_ab` (`:231`), `repair_reorder_pnr_ab` (`:354`) are proved for the live model. `Abort.v` builds `E2`, proves it has **no** halted world (`E2_no_halted`), exhibits `inert` worlds, and gives a conforming session `Gguarded_inhabited` (`Abort.v:195`) plus `Gguarded_bridge_nonvacuous`. This is exactly what R4 asked for and it is done properly. **But** the entire post-abort safety of *both* repairs is `safeT_inert` (`Repairs.v:113`) — see probe **P8**: on a runtime that matches the paper's own prose gloss but does not freeze, both repairs fail at every budget. |
| **W2** | `✓φ` dead syntax with a live premise | **NOT FIXED structurally; FIXED by honest disclosure** | `CT_Goal` still carries `phi W` (`Bridge.v:50`). What is new is a payback theorem (`markers_are_met`, `:273`) and a real instance (`Ggoal_inhabited`, `Ggoal_marker_met`), plus a plain statement of the consequence at `main.tex:766–772`: "marking the goal on such a branch leaves the protocol uninhabited there… our benchmark uses no inline markers". Probe **P4** confirms the disclosure is exactly accurate and not an over-cautious hedge. The φ/Φ conflation R4 named is also addressed in one sentence (`main.tex:764–766`). I accept this as addressed, and downgrade it from blocking to a design objection. |
| **W3** | μ-layer has no judgment; contractiveness unmechanized; abstract overclaims | **FIXED** | `safeR` (`Mu.v:545`), `TR_sound`/`TR_complete`/`TR_exact`, `TC_is_TR` (`:1275`) — a genuine conservative-extension result — and `decide_mu_judgment`. `gd`/`hguard`/`pre`, `progress_mu`, `contractiveness_is_necessary`, `unguarded_goal_stuck`; `main.tex:977–998` is now the best-argued page in the paper. Composition is explicitly disclosed as finite-fragment-only (`main.tex:1025–1028`). Residual presentation issue in W6 below. |
| **W4** | T-Narrow sold as internal-choice covariance | **FIXED, and turned into a result** | `ctypes_comm_labels`, `narrowing_breaks_conformance`, `narrowing_asymmetry` (`Bridge.v:623,634,646`); `main.tex:655–668` now states the asymmetry as the point. This is the round-2 request answered better than it was posed. |
| **W5** | Repairs proved at the root, applied at nested paths | **FIXED for three of four** | `safeT_congruence` (`Repairs.v:436`) is real and general (hole under actions, markers, any branch, with the branch list split as `pre ++ … :: post`), and the price is disclosed (`main.tex:1495–1501`). `repair_narrow_anywhere` / `repair_reorder_anywhere` / `repair_compensate_anywhere` are clean. **`repair_guard_anywhere` (`:477`) is not instantiated anywhere and its first hypothesis is refuted for the paper's own `E2`** — probes **P2**, **P3**. |
| **W6** | \Ben{} angelic, read as a guarantee | **FIXED, exemplary** | The "two quantifiers" paragraph (`main.tex:539–553`) says exactly what R4 asked; `assuredP` (`Severity.v:419`) requires enabledness *and* universal quantification over affordable deviations, `Robust`, `robust_benign`, `assured_downward` with the correct (opposite) monotonicity, `benign_is_not_robust` for strictness, and `Ggood_is_robust` (`Bridge.v:791`) for inhabitation. I re-proved `Ggood_is_robust` independently before finding the authors' version; they agree. |
| **W7** | Kernel decides a different goal predicate | **PARTLY fixed; one sentence is now FALSE** | `goal_reach_implies_reach_mu` (`Kernel.v:254`) and `goal_reach_strictly_stronger` (`:267`) are new and correct, and `main.tex:1094–1097` discloses the mismatch. But `main.tex:1097–1099` — "The kernel's notion is therefore the stronger one, so a \Ben{} verdict computed with it errs towards \Fut{} and never the other way" — is **refuted by probe P1**, and the mismatch is not confined to severity labels: `elab` derives *both* the rational default guards *and* the derived hazard bits from the same `gr = goal_reachable` (`Kernel.v:306,318,331`). |
| **W8** | Cone of influence asserted, not proved | **FIXED as a theorem; the tool-side gap remains, and is disclosed** | `reach_cone`/`safeT_cone`/`interface_projection` (`Severity.v:368,390,403`) with a non-degenerate instance (`cone_is_not_degenerate`, `Bridge.v:851`). `main.tex:1029–1033` says plainly that the syntactic cone the tool computes is a front-end property, not a theorem. Residual in W5 below. |
| **W9** | No principal/minimal-budget theorem | **FIXED** | `principal_characterises`, `principal_unique`, `principal_exists` (`Severity.v:273,286,300`), cited as thm:principal (`main.tex:670`). One phrasing slip (W7 below). |
| **W10** | Residual overclaims (6 items) | **4 of 6 fixed** | Abstract's kernel sentence weakened to "cross-checked"; prefix-closure mechanized at the finite layer (`hrun_split`, `bridge_every_configuration`); the comm/comm swap display now shows the full product and the text explains it (`main.tex:836–845`); non-vacuity scope stated. Two survive plus one new one — W8 below. |

**Summary of PART 1.** Eight of ten are genuinely fixed, two of them (W4, W6) better than asked.
This is the most responsive revision round of the three. What follows is what a hostile PC
member will still find, in the order they will find it.

---

## (b) The probes

All compile against the shipped `.vo` with `coqc -Q proof "" P.v`; all print
`Closed under the global context`.

### P8 — **the guard and reorder repairs are sound only because the abort world freezes the runtime for ever**

`main.tex:1546–1549`: "An abort world is not a world where nothing is enabled. It is a world
where everything is enabled and nothing changes: the runtime keeps answering tool calls and the
answers are errors."

`Repairs.v:79`: `Definition idle (W : World) : Prop := forall a W', E a W W' -> W' = W.`

Those are not the same claim. "The answers are errors" is a statement about *the validation*;
`idle` is a statement about *every capability, for ever* — an idle world has itself as its only
successor, so nothing in the session can ever change again. `E4` below is the runtime the prose
describes: the validation is live and diverts to an abort world; the other tools go on working.

```coq
Definition E4 : Ctx := fun a W W' =>
  (a = 1 /\ W' = wupd W verified 1) \/
  (a = 2 /\ W' = wupd W booked 1) \/
  (a = 3 /\ W verified = 1 /\ W' = W) \/
  (a = 3 /\ W verified <> 1 /\ W' = wupd W aborted 1).

Theorem E4_validates_everywhere : forall W, validates_ab E4 3 psi2 ab2 W.
Theorem E4_has_no_halted_world  : forall W, ~ halted E4 W.
Theorem E4_abort_not_idle       : ~ idle E4 (ab2 W2).
Theorem guard_fails_without_the_freeze   : ~ safeT E4 Haz0 1 Gguarded W2.
Theorem reorder_fails_without_the_freeze : forall k, ~ safeT E4 Haz0 k (GAct 3 1 (GAct 2 1 GEnd)) W2.
```

Note what `E4` gets *right* that `E2` does not: it satisfies `validates_ab` at **every** world,
not only live ones. It has no halted world. Its validation is a validation. The single thing it
does not do is stop `purchase` from purchasing after a failed check — and that is enough to
destroy both repairs, at every budget.

So the mechanized content of `thm:guard` and `thm:reorder` is: *a guard repairs a branch exactly
when a failed validation aborts the session*, not merely the call. That is a defensible and
interesting position — it makes `guard` a runtime narrowing that keeps the branch available when
intended — but it is not what §10 says, and it is the assumption on which the paper's applied
contribution rests. Both repairs discharge their misselection case with the same one-line
appeal (`Repairs.v:207` and `:369`: `apply safeT_inert`), so this is a single point of failure,
not two.

### P1 — **the kernel's goal notion is not conservative, and `main.tex:1097–1099` is false**

```coq
Definition actP : Act := {| a_pre := FTrue; a_add := [0]; a_del := []; a_haz := [] |}.
Definition GP : Gr Gd := RComm Gd 0 1 [(0, @nil Wd, RAct Gd 0 0 (REnd Gd))].  (* guard never holds *)

Theorem kernel_says_goal_reachable :
  goal_reach 1 [actP] (FAtom 0) GP [false;false].
Theorem theory_says_goal_unreachable_at_0 :
  ~ reach_mu Wd Gd satg (Ek 1 [actP]) (fun v => satf (FAtom 0) v = true) 0 GP [false;false].
Theorem theory_says_no_hazard_at_0 :
  ~ reach_mu Wd Gd satg (Ek 1 [actP]) (Hazk 1) 0 GP [false;false].
```

The two notions differ on **two** axes, in **opposite** directions. `goal_reach` requires
reaching `REnd` (stronger); `goal_reach` spends no budget and walks `succ1` edges for free
(weaker). §8 argues only the first and concludes a one-way error. The probe is the second: at
budget 0 the theory's verdict for `(GP, w)` is \Fut{} (no hazard, no goal) and the kernel's goal
oracle says the goal is reachable. That is precisely "the other way".

Worse, the consequence is not limited to severity labels, as `main.tex:1124–1126` claims.
`elab` (`Kernel.v:306,318,331`) computes with `gr = goal_reachable` **both**
- the derived hazard table `hz_tbl := filter (fun w => negb (gr P cont w)) worlds`, and
- the *default rational guards* for any branch with no explicit guard.

Guards decide which branches are misselections. So `gr` fixes what counts as a deviation and
what counts as a hazard, and therefore fixes `k*` itself. The 499/499 differential test cannot
see this: the analyzer and the kernel share no code but share the definition. `main.tex:1121–1126`
("the strongest evidence… It is evidence about `k*` and about the hazard") should be weakened to
"evidence that two independent implementations of *this* elaboration agree", with the
elaboration's goal notion named as the trusted input it is.

### P2 / P3 — **`repair_guard_anywhere` has no instance, and cannot have `E2` as one**

`Repairs.v:477` requires `forall W', validates_ab E a psi ab W'` — at *every* world, the abort
world included. The authors' own comment at `Repairs.v:47–49` says a global version "would force
the equation to hold inside the abort world too, where it is false". `repair_guard_anywhere` is
the global version.

```coq
Definition Wodd : World := fun x => if Nat.eq_dec x aborted then 5 else 0.
Theorem E2_is_not_globally_validating : ~ (forall W, validates_ab E2 3 psi2 ab2 W).

Theorem anywhere_forces_idempotent_abort :
  forall E a psi ab W,
    (forall W', validates_ab E a psi ab W') -> idle E (ab W) -> ~ psi (ab W) ->
    ab (ab W) = ab W.
```

The second theorem is the structural obstruction: with a global `validates_ab` and an idle abort
world, the abort map must be idempotent **on the nose** (Coq equality of world *functions*),
which `ab2 W = wupd W aborted 1` is not. So the abort map must in practice be a constant. It
*can* be — P3 exhibits a witness so the corollary is not vacuous —

```coq
Definition Wab : World := fun _ => 7.
Definition ab3 : World -> World := fun _ => Wab.
Theorem E3_validates_everywhere : forall W, validates_ab E3 3 psi3 ab3 W.
Theorem E3_abort_inert : forall W', ~ Haz0 W' -> inert E3 Haz0 (ab3 W').
Theorem E3_branch_safe : forall b' W', psi3 W' -> safeT E3 Haz0 b' GEnd W'.
Corollary repair_guard_anywhere_is_instantiable : (* the corollary applied, at an arbitrary C *)
```

— but the paper never says the abort map must be a single world, and the runtime it *does*
build cannot be used with the corollary it *does* cite. Against `main.tex:1490–1494` ("All four
repairs therefore apply at nested positions, which is where the tool applies them") and the new
`main.tex:320–322` ("the cone-of-influence and congruence theorems are instantiated where their
hypotheses could have been satisfiable nowhere"), this is the one corollary that needed the
check and did not get it.

### P4 — **a goal marker on any misselectable branch that can lose the goal leaves the protocol uninhabited**

```coq
Definition FastGoal : Gt := GAct 2 1 (GGoal Phi0 GEnd).
Definition Gmiss : Gt :=
  GComm 0 1 [ (10, (fun _ : World => True),  SafeGoal) ;
              (11, (fun _ : World => False), FastGoal) ].
Theorem Gmiss_is_0_tolerant : safeT E0 Haz0 0 Gmiss W0.
Theorem Gmiss_uninhabited   : forall s, ~ ctypes E0 Gmiss s W0.
```

This confirms `main.tex:766–772` is accurate rather than cautious. The two halves together are
the objection: `safeT` **accepts** `Gmiss` and `ctypes` **rejects every session for it**, so the
marker is inert in the condition and fatal in conformance, and the artifact's only marker
witness (`Ggoal`) has a single branch guarded by `True` — i.e. a protocol with no misselection at
all. The authors' own in-flight `two_role` inhabitation construction excludes `GGoal` for exactly
this reason ("a marker is an assertion about the world, so no construction uniform in the world
can discharge it"). A construct that cannot be placed anywhere the paper's subject matter arises
is decoration; R4's option (b) — delete `✓φ` and keep `Φ` — still costs an afternoon and loses
nothing measured.

### P5 — **three statement-vs-prose gaps, one to eight lines each**

```coq
(* a *) Theorem guard_decidability_is_excluded_middle :
  (forall (psi : World -> Prop) (W : World), psi W \/ ~ psi W) -> forall P : Prop, P \/ ~ P.

(* b *) Theorem every_configuration_really : forall Ec Hz G s W b tr1 tr2 G1 s1 W1 G' s' W',
  ctypes Ec G s W -> safeT Ec Hz b G W ->
  hrun Ec G s W tr1 G1 s1 W1 -> hrun Ec G1 s1 W1 tr2 G' s' W' -> total tr1 + total tr2 <= b ->
  ~ Hz W1 /\ ctypes Ec G1 s1 W1 /\ safeT Ec Hz (b - total tr1) G1 W1.

(* c *) Theorem MBad_really_misselects :
  (forall (psi : World -> Prop) (W : World), psi W \/ ~ psi W) ->
  forall W, exists s', hstep E0 Gbad MBad W FastPath s' W 0 1.
```

(a) Assumption 1 (`main.tex:500–506`) says decidability "is a hypothesis of the affected lemmas,
never an axiom: the development uses no classical principle". The hypothesis actually carried by
`progress`, `every_label_steps`, `MBad_takes_the_wrong_branch` and all of `Repairs.v`'s section
quantifies over *arbitrary* world predicates, so it entails full excluded middle in one line. The
distinction "hypothesis, not axiom" is real and worth keeping; the words "no classical principle"
are not. Restrict the hypothesis to the guards actually appearing in the protocol, or drop the
claim.

(b) `bridge_every_configuration` (`Bridge.v:737`) concludes `exists G1 s1 W1, hrun … tr1 … /\ ~ Hz W1`.
The prose (`main.tex:713–716`) is universal — "no configuration is a hazard state". The universal
form is three lines from `bridge_run`, as shown. Also: the prefix-closure upgrade was applied only
to the finite bridge; `thm:bridge-mu` (`main.tex:827–835`) and `thm:bystander` (`:845`) keep the
same "hazard-free on every run" wording over endpoint-only lemmas (`bridge_mu_safeR`,
`bridge_interleaved`), and there is no `hrun_split` for `Mu.hrun` or `irun`.

(c) `MBad_takes_the_wrong_branch` leaves the cost existential, so it proves a step to `FastPath`
exists, not that it is a *misselection*. `main.tex:730–732` says "that really does take the
misselected branch". Pinning `c := 1` is one `inversion`.

### P6 — confirmation, not a finding

I proved `Robust E0 Haz0 Phi0 k Ggood W0` independently before discovering `Ggood_is_robust`
(`Bridge.v:791`) already in the artifact. W6 is fully discharged. `check_bridge.v` covers it.

---

## (c) Score

**B — weak accept. Confidence 4/5.** Up from R4's C.

The reason for the move: R4 conditioned B on three things — fix or delete the false sentence in
§10, give the guard repair a soundness theorem and an inhabitation witness for the aborting
model, and resolve `✓φ`. The first two are done, properly and with the vacuity check R4 demanded
(`E2_no_halted`, `Gguarded_inhabited`, `Gguarded_bridge_nonvacuous`). The third is resolved by
disclosure rather than by deletion, which I accept. On top of that the authors delivered W3,
W4, W5, W6, W8 and W9 — a coinductive judgment with a conservative-extension theorem, the
narrowing asymmetry as a *result*, a real congruence lemma, the angelic/demonic separation with
a strictness witness, a mechanized cone with a non-degenerate instance, and principality of
`k*`. That is a large amount of correct new metatheory in one round, and the disclosure
discipline (`main.tex:766–772`, `:1025–1028`, `:1029–1033`, `:1094–1097`, `:1495–1501`) is now
consistently good.

The reason it is not A, and the reason a hostile PC member could still argue C: the paper
contains one sentence that is provably false in thirty lines of Coq (`main.tex:1097–1099`,
probe P1), and the repair section's applied claim rests on a runtime assumption that the paper
glosses as ordinary and that probe P8 shows is load-bearing. Both are *sentences*, not theorems;
neither requires new mathematics to fix. If they are left as written, the next reviewer who runs
P1 will discount §8 wholesale and the paper drops back to C. If they are fixed as described
below, I would argue for B+ in committee and would not object to A.

---

## (d) Remaining weaknesses, ranked by how much each moves a PC member

### W1 — **MAJOR.** The guard and reorder repairs require the runtime to freeze, and the paper says otherwise
*Evidence:* probe P8; `Repairs.v:79,113,207,369`; `main.tex:1546–1549`.

`inert` is not "the answers are errors"; it is "no capability ever changes anything again". `E4`
satisfies `validates_ab` globally (which `E2` does not), has no halted world, and breaks both
repairs at every budget. Everything the misselected branch gets is `safeT_inert`, and
`safeT_inert` is true because nothing can happen.

**Concrete fix**, in three parts, all cheap. (i) State the obligation: *the guard repair is sound
exactly when a failed validation aborts the session — the gate must stop honouring the
remaining calls, not merely fail the check.* Say that this makes `guard` a runtime narrowing
that stays available when intended, which is a good thing to be able to say. (ii) Put `E4` in
`Abort.v` as a **non-example** with `guard_fails_without_the_freeze`, next to `E2`; it is 40
lines and I have written them. (iii) Check the benchmark: `email_campaign_guarded` and the
`guarded shipping choice` are scored as repairs — say whether the runtimes they model abort the
session on a failed check, because if they do not, Table 3's repair rows are measuring `E4`.

### W2 — **MAJOR.** `main.tex:1097–1099` is false, and the kernel's goal notion reaches `k*`, not just the labels
*Evidence:* probe P1; `Kernel.v:184,254,267,306,318,331`; `main.tex:1094–1099,1121–1126`.

Two independent points. The conservatism claim is refuted. And because `elab` derives the
default rational guards *and* the derived hazard bits from the same unbudgeted, run-to-completion
`gr`, the mismatch is not quarantined in the severity labels: it fixes which branches are
misselections and which worlds are hazardous, hence `k*`.

**Concrete fix.** Delete "so a \Ben{} verdict computed with it errs towards \Fut{} and never the
other way" and replace with: *the two notions are incomparable — `goal_reach` is stronger on the
end condition and weaker on the budget — so we do not claim a direction.* Then either (a) add the
budget component to `gsucc` and change `goal_hit` to `satf goal (snd s)`, which makes the
kernel's notion the theory's and is the smaller change, or (b) weaken `main.tex:1121–1126` to say
the differential test is evidence about the *implementations* of a shared elaboration, whose goal
notion is a trusted input. (a) is worth doing: it is a day's work and it turns §8's headline from
"two implementations agree" into "the tool computes the quantity the theory defines".

### W3 — **MAJOR (small).** `repair_guard_anywhere` is the one hypothesis set the vacuity check missed
*Evidence:* probes P2, P3; `Repairs.v:47–49,477`; `main.tex:320–322,1490–1494`.

The corollary the paper cites for "the repairs apply where the tool applies them" cannot be
instantiated with the paper's own runtime, and its hypotheses force the abort map to be constant.
The introduction's new vacuity paragraph claims the congruence theorems are instantiated; the
congruence *theorem* is (trivially — its hypothesis is a plain implication), the guard *corollary*
is not.

**Concrete fix.** Either weaken `repair_guard_anywhere` to take `validates_ab` only at the worlds
the context can reach (a hypothesis of the shape `forall W', reachable C W' -> validates_ab … W'`
— you already carry `ends`, which gives you the reachable set), or add P3's constant-abort
witness to `check_repairs.v` and state in one sentence that the off-root guard repair needs a
single global abort world. Do not leave the corollary uninstantiated in a paper whose
introduction advertises that it instantiates such things.

### W4 — **MODERATE.** `✓φ` is now honestly labelled decoration
*Evidence:* probe P4; `Bridge.v:50,273`; `main.tex:764–772`.

`safeT` accepts a protocol whose marker sits on a losable misselectable branch; `ctypes` rejects
every session for it; the payback theorem therefore has nothing to say about exactly the
configurations the paper's severity trichotomy exists to classify. The disclosure is correct and
the benchmark does not depend on it, which is why this is moderate and not blocking. But three
sections of syntax, four relations threaded with an inert constructor, and a general inhabitation
construction that has to exclude it, is a lot of surface for a construct with no use.

**Concrete fix.** Delete `✓φ` from `Gt`, `Gr`, `safeT`, `reach_haz`, `ctypes`, `hstep` and the
swap relation; keep `Φ` as the severity parameter; keep one paragraph in Future Work saying what
a premise-free `CT-Goal` plus a run-level marker obligation would buy. This *shortens* the paper
and removes the only place where the condition and conformance disagree about which protocols are
sensible.

### W5 — **MODERATE.** The cone hypothesis is stronger than the tool's cone can justify
*Evidence:* `Severity.v:337–342`; `Bridge.v:809–860`; `main.tex:1018–1033`.

`cap_cone` demands a `V`-bisimulation for **every** capability of `Γ`, not only those in the
remainder — so a capability that can still fire elsewhere in the pack, reading outside `V` and
writing inside it, kills the hypothesis. The tool takes `V` syntactically from the remaining
segments' predicates. The gap is disclosed, but the disclosure is one sentence and Table 2's
entire projected column (48 queries and 2 interface points at n=6 against 566 and 1149) depends on
it. The instance `V0` (`Bridge.v:806`) is a runtime whose two capabilities are enabled everywhere
and touch exactly the cone, i.e. the easy case; nothing exercises a precondition reading outside
`V`.

**Concrete fix.** `Interleave.v` already has `supported`, `footprint`, `strips_preserves`,
`strips_neutral`, axiom-free. Derive `cap_cone` from them for STRIPS capabilities whose footprint
is inside `V`, restrict the quantifier to the capabilities of the remainder, and instantiate the
cone on one benchmark protocol where `V` is a proper subset. That converts "a property of the
front end" into a checkable side condition.

### W6 — **MODERATE.** `safeR` is a transition-directed invariant sold as a syntax-directed rule
*Evidence:* `Mu.v:545,583`; `main.tex:174–176,956–966`.

`safeR` has **one** rule, quantified over `mstep0`/`mstep1`; the case analysis that makes `safeT`
syntax-directed lives in the step relation. `TR_complete` is four lines by `cofix`, because
`safeR` *is* the greatest fixpoint of `¬reach_mu` by construction. The content is real —
`TC_is_TR` is a genuine conservative-extension theorem and the coinductive proof principle is
usable — but the paper never displays the rule, says "read T-Choice-Safe coinductively" as though
the five finite rules survive, and the abstract's "One syntax-directed rule characterizes the
condition exactly" now has two referents. Also the abstract still bundles interface composition
with recursion in one sentence, though `thm:seq` correctly says composition is finite-fragment
only.

**Concrete fix.** Display the `SR_step` rule; add one clause — *at the recursive layer the rule is
directed by the transition relation rather than by the syntax, which is what lets `μ` unfolding be
a silent step*; and split the abstract sentence so that "syntax-directed", "survives recursion" and
"composes against an interface" name the layers they hold at.

### W7 — **MINOR.** Statement-vs-prose gaps
*Evidence:* probe P5; `Bridge.v:737,757`; `Severity.v:300`; `main.tex:500–506,713–716,730–732,827–835,845,675`.

1. Assumption 1's Coq form is excluded middle (P5a); "the development uses no classical principle" overstates.
2. `bridge_every_configuration` is existential where the prose is universal (P5b, three lines).
3. `MBad_takes_the_wrong_branch` leaves the cost existential (P5c, one line).
4. Prefix closure was fixed at the finite layer only; `thm:bridge-mu` and `thm:bystander` keep the same wording over endpoint-only lemmas. Two `hrun_split` analogues, ~8 lines each.
5. `principal_exists` also requires `safeT 0 G W`; `thm:principal`'s "one exists whenever tolerance is finite and the question is decidable" omits it. A residual that is not even `0`-tolerant has no principal `k`, which is a case the tool must report.
6. `check_repairs.v` runs `Print Assumptions` on `idle`, a `Definition`. Harmless, but it pads the count the draftnote quotes.

### W8 — **MINOR.** The guard repair's worked instance never exercises the intended branch
*Evidence:* `Abort.v:168–181`.

`Gguarded_is_k_tolerant` is proved at `W2`, where `psi2` fails; the intended-branch obligation is
discharged by `exfalso`. So the half of the repair the paper sells as its advantage over
narrowing — "keeping it available when it is intended" — is covered only by the general
`repair_guard_exact_ab`, never by the worked example. One more lemma at a world with
`verified = 1` closes it and would make the booking story complete in both directions.

---

## (e) The single highest-value remaining change

**Publish `E4` as a non-example, and say what the guard and reorder repairs actually require of
the runtime.**

Concretely: add `E4`, `E4_validates_everywhere`, `E4_has_no_halted_world`, `E4_abort_not_idle`,
`guard_fails_without_the_freeze` and `reorder_fails_without_the_freeze` to `Abort.v` and
`check_abort.v`; rewrite `main.tex:1546–1549` to say that an abort world is one in which *the
gate stops honouring calls*, not one in which one call returns an error; and add one sentence to
`thm:guard` and `thm:reorder` naming that as the runtime obligation the repairs impose.

I single this out over W2 and W3, which are individually cheaper, for the reason the paper itself
gives. §11 says the predecessor discipline was withdrawn because a mechanized audit found a
premise that could not be satisfied, and §1 (as of `32ddf72`) now advertises that this paper
checks every theorem for vacuity. The round-2 audit asked "is `inert (ab W)` satisfiable?" and the
authors answered it excellently, with `E2`. The question that audit did not ask is the one that
decides whether the repair is a repair: **is `inert` doing all the work?** It is. A discipline
whose stated methodology is to hunt for premises that hold for the wrong reason should hunt for
this one itself, in print, and it will be *stronger* for it — "a guard repairs a branch exactly
when the gate aborts the session on a failed check" is a sharper and more useful claim than "a
guard repairs a branch". Add P1's counterexample to §8 in the same pass and the two false
sentences in this paper become two correct ones.

*Second-best, if the authors want a theory contribution instead:* W2's option (a) — put the
budget into `gsucc` and drop the `REnd` requirement from `goal_hit`. That makes the kernel decide
the theory's quantity, upgrades §8's differential test from "two implementations agree" to "the
tool computes what the theory defines", and removes the last place where the paper's headline
number `k*` depends on a notion the metatheory does not define.

---

### Reproduction

Six probe files, thirteen results, all `Closed under the global context`:

```
cd proof && coqc -Q . "" P1.v   # kernel goal notion is not conservative
                       P2.v   # E2 is not globally validating; the structural obstruction
                       P3.v   # repair_guard_anywhere is instantiable, by a CONSTANT abort map
                       P4.v   # a marker on a losable misselectable branch is uninhabited
                       P5.v   # EM, the universal every-configuration form, the cost-1 step
                       P8.v   # E4: both repairs fail without the freeze
```

Coq 8.18.0, stdlib only, run against the shipped `.vo`. No file in `proof/` or `main.tex` was
modified, and nothing was committed.
