# ECOOP review — R8 (theory and mechanization, FOURTH ROUND)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Reviewer expertise:** behavioural types, MPST, concurrency, mechanized metatheory.
**This is round 2 of my own review** (R5 was round 3 of the paper's cycle).

**Snapshot reviewed.** `main.tex` and `proof/` at `50a2522` ("Close the review's minor findings,
and buy back a page"), with the shipped `.vo` built 23:02–23:03. The tree moved once during the
review, to `95a9cca` ("Tie every stated number to the file it came from"); that commit touches
only evaluation numbers and `results/`, no `.v` file and no theory prose, so every finding below
is unchanged against it. Line numbers are those of `50a2522`/`95a9cca`; the quoted sentence, not
the number, is the anchor.

**Method.** I did not take the rebuttal's word for anything. I `Check`ed the elaborated statement
of every result the round-4 response names, read the full diff of `Abort.v`, `Bridge.v`,
`Repairs.v`, `Interleave.v`, `Kernel.v` since `8abfa04`, re-ran `scripts/dump_statements.py` and
`scripts/check_paper_citations.py`, read the shipped benchmark corpus and the kernel elaborator,
and wrote **seven new probe files**. All seven compile against the shipped `.vo` with
`coqc -Q proof "" P.v` and every result in them prints `Closed under the global context`. No file
in `proof/` and no line of `main.tex` was modified; `STATEMENTS.md` was regenerated to a copy and
the original restored (`git status` clean).

---

## (a) PART 1 — verification of the round-3 revisions

| R5 item | Claimed | Verdict | Evidence |
|---|---|---|---|
| **Major 1** — the repairs rest on the runtime freezing, and §10 says otherwise | `E4` published as a non-example; prose rewritten | **FIXED, and done exactly right** | `Abort.v:296–392` carries `E4`, `E4_validates` (at *every* world), `E4_no_halted`, `E4_not_idle` (stated more generally than I asked: `forall W, W booked = 0 -> ~ idle E4 W`), `Gguarded_not_1_tolerant_in_E4`, `reordered_not_tolerant_in_E4`; all six are in `check_abort.v`. `main.tex:1602–1613` now says *"\emph{Idle} is not `the runtime answers and the answers are errors': it is `the session is over'"* and *"a deployment that only errors the call does not get the theorem"*. This is the sharper claim I said it would be. Part (iii) of my fix — check the benchmark's repair rows — was not done, and doing it turns up **N3** below. |
| **Major 2** — "errs towards \Fut{} and never the other way" is false, and the mismatch reaches $\kstar$ | sentence deleted; `goal_reach_ignores_the_budget` added; incomparability + $\kstar$ stated | **FIXED** | The sentence is gone. `Kernel.v:278–307` proves `goal_reach 1 [act_set0] (FAtom 0) Gmiss [false;false] /\ ~ reach_mu … 0 …`, i.e. my P1's second axis, as a theorem of theirs. `main.tex:1110–1123` states incomparability with a witness for each direction, then: *"the elaboration derives the rational default guard and the derived hazard bit from the same notion … and $\kstar$ is computed against it"*, and weakens the differential test to *"what the agreement establishes is that they agree, not that the convention is the paper's $\Phi$-reachability"*. That is option (b) of my fix, stated without hedging. Option (a) — putting the budget into `gsucc` — is still the better paper, but (b) is honest and sufficient. |
| **Major 3** — `repair_guard_anywhere`'s hypotheses are the set the vacuity paragraph missed | `global_abort_is_idempotent` added; constraint stated | **PARTLY FIXED, by disclosure** | `Repairs.v:493–507` is exactly my P2 obstruction, proved by them: a globally-validating validation into an idle abort world forces `ab (ab W) = ab W` on the nose. `main.tex:1574–1582` states it and admits *"the runtime we build instantiates the root-level version"*. The corollary still has **no instance**, and still cannot have `E2` as one (probe **R8-P5** re-proves `~ (forall W, validates_ab E2 3 psi2 ab2 W)` against the current tree). The sentence at `main.tex:1570–1572` — *"All four repairs therefore apply at nested positions, which is where the tool applies them"* — is still ahead of the evidence for one of the four, but the correction follows two lines later. Downgraded to minor. |
| **Moderate 4** — the goal marker is decoration | `Gmiss_safe`, `Gmiss_uninhabited`; cost stated beside benefit | **FIXED as disclosure** | Both exist (`Bridge.v:1069–1104`), both audited. `main.tex:793–804` states the gap in four sentences and says the benchmark uses no inline markers. `two_role`'s exclusion of `GGoal` is now named as the same phenomenon seen from the other side. One under-statement: `Gmiss_safe` is proved at budget **0**, the one budget at which `ST_Comm`'s deviation clause is unreachable, so the example does not actually show the condition tolerating a marker on an *affordable* misselection. Probe **R8-P2** supplies the all-budget version in three lines. |
| **Moderate 5** — `cap_cone` has no bridge from the STRIPS footprints | `strips_haz_cone`, `strips_cap_cone`, `strips_safeT_cone` | **HALF FIXED; the half that mattered is still open** | The three lemmas are real, axiom-free, and give a genuinely syntactic sufficient condition — and the observation that only *preconditions* need to be in the cone, not writes, is a nice one that the prose now makes (`main.tex:1063–1066`). But all three inherit the quantifier I objected to: the containment is demanded of **every** capability of the table, not of the capabilities the residual can still use. Probe **R8-P3** refutes both the syntactic hypothesis and the semantic `cap_cone` on a table where one *unused* tool reads outside the cone, while the conclusion those hypotheses exist to deliver holds anyway. Probe **R8-P4** proves the restricted version. See **N2**: because `TC_seq_interface` shares one $\Gamma$ across $G_1$ and $G_2$, this is not a corner case, it is the composition setting. Still no instance in which $V$ is a proper subset and any capability has a non-trivial precondition (`V0`'s two capabilities are enabled everywhere). |
| **Moderate 6** — `safeR` is transition-directed, sold as syntax-directed | *(not claimed)* | **NOT FIXED** | `Mu.v:545–550` still has the single `SR_step` rule quantified over `mstep0`/`mstep1`; the paper still says *"Read \textsc{T-Choice-Safe} coinductively"* (`main.tex:974`) and never displays the rule; the abstract still reads *"One syntax-directed rule characterizes the condition exactly"* (`:173`) with two referents, and still bundles *"composes against an interface … and is decidable for regular protocols"* in one sentence although `thm:seq` is finite-fragment only. |
| **Minor 7.1** — `bridge_every_configuration` existential where the prose is universal | universal, with `bridge_prefix` beside it | **FIXED** | `Check` gives the universal form; `bridge_prefix` is new and is strictly stronger than the prefix statement (it quantifies over *any* `tr1`-run, not only the prefix of the given one). |
| **Minor 7.2** — `MBad_takes_the_wrong_branch` leaves the cost existential | cost pinned at 1 | **FIXED, better than asked** | `Check` gives `forall W, exists s', hstep E0 Gbad MBad W FastPath s' W 0 1` — the cost is pinned **and** the excluded-middle hypothesis is gone, because the proof now builds the step directly instead of routing through `every_label_steps`. |
| **Minor 7.3** — `principal_exists`'s 0-tolerance hypothesis unstated | stated | **FIXED** (`main.tex:686–688`, `Severity.v:300`). |
| **Minor 7.4** — Assumption 1's "no classical principle" | caveat added | **FIXED, and well** | The assumption block now says the hypothesis *"is excluded middle for that class, discharged by the caller rather than assumed globally, and a reader should judge those lemmas as classical in content and constructive only in bookkeeping"*. That is the right sentence. |
| **Minor 7.5** — prefix closure fixed at the finite layer only | *(not claimed)* | **NOT FIXED** | `grep` finds `hrun_split` and nothing analogous for `Mu.hrun` or `irun`. `thm:bridge-mu` (`:841–849`) and `thm:bystander` (`:882–889`) still say "every run" over endpoint-only lemmas. ~8 lines each. |
| **Minor 7.6** — `Print Assumptions idle` on a `Definition` | *(not claimed)* | **NOT FIXED** | `check_repairs.v:19`. It pads the audited count by one. |
| **R5-W8** — the guard repair's worked instance never exercises the intended branch | *(not claimed)* | **NOT FIXED** | `Gguarded_is_k_tolerant` is still proved only at `W2`, where `psi2` fails, so the intended-branch obligation is discharged by `exfalso`. Probe **R8-P6** supplies the missing lemma at a verified world (25 lines). |
| **New this round** — `canon`/`canon_conforms`/`two_role_bridge_nonvacuous` | inhabitation as a construction | **REAL, but its side conditions are under-reported** — see **N4**. |
| **Housekeeping** | `check_paper_citations.py` | **CLEAN**: 139 cited results, all defined, all covered by a `Print Assumptions` harness; no `Axiom`, `Admitted` or `admit` anywhere in `proof/`. |

**Summary of PART 1.** Both blocking majors are fixed, one of them (Major 1) in precisely the form
I asked for and with the non-example published as a first-class result. Major 3 and Moderate 4 are
fixed by honest disclosure. Moderate 5 is half done; Moderate 6 is untouched. Four of six minors
are closed and two of those are better than requested. This is again a responsive round, and the
disclosure discipline is now the best thing about the paper. What follows is what is left, and
what the round introduced.

---

## (b) The probes

All compile with `coqc -Q proof "" P.v` against the shipped `.vo`; every result prints
`Closed under the global context`.

### R8-P1 — **`two_role` is not "two-role"; it also fixes the direction of every choice**

`main.tex:746`: *"Every two-role protocol is inhabited, over any runtime in which a tool call
always has an answer."* `main.tex:760`: *"Two side conditions are exactly the two places the
general case is harder."*

`Bridge.v:644–652` says otherwise:

```coq
| GComm p q brs => p = 0 /\ q = 1 /\ brs <> nil /\ NoDup (labels brs) /\ …
| GAct _ p G0   => (p = 0 \/ p = 1) /\ two_role G0
| GGoal _ _     => False
```

There are **four** side conditions, not two: distinct labels, no markers, non-empty branch lists,
and — the substantive one, unmentioned — *role 0 sends and role 1 receives at every single
choice*. A protocol in which the second role ever chooses is outside the theorem.

```coq
Definition Galt : Gt :=            (* 0 chooses; then 1 answers *)
  GComm 0 1 [ (10, (fun _ : World => True),
               GComm 1 0 [ (20, (fun _ : World => True), GEnd) ]) ].

Theorem Galt_is_outside_two_role : ~ two_role Galt.
Theorem reversed_choice_is_outside_two_role :
  ~ two_role (GComm 1 0 [ (30, (fun _ : World => True), GEnd) ]).
Theorem Galt_is_inhabited_by_canon : forall W, ctypes E0 Galt (sess_of Galt) W.
```

The third result is the point: `canon` conforms for `Galt` anyway. The restriction is bookkeeping
in `canon_other` (which needs to know which two role indices are live), not a projection
obstruction, so `p = 0 /\ q = 1` can be relaxed to `{p,q} = {0,1}` with a symmetric case split.
It matters because the paper's own benchmark contains such a protocol: `order_fulfilment` has two
choosers, `agent` and `bank` (the environment-choice example the paper singles out).

### R8-P2 — **`Gmiss_safe` is stated at the one budget where the deviation clause is vacuous**

```coq
Theorem Gmiss_safe_at_every_budget : forall k, safeT E0 Haz0 k Gmiss W0.
Corollary the_gap_at_every_budget : forall k,
  safeT E0 Haz0 k Gmiss W0 /\ forall s, ~ ctypes E0 Gmiss s W0.
```

At `b = 0` the deviation clause of `ST_Comm` is discharged by `discriminate` — the misselection
into the marked branch is not affordable, so nothing about markers is being tested. The all-budget
version is three lines (above) and is what `main.tex:795–797` actually asserts ("$\vdash_b$ treats
a marker as transparent"). Use it.

### R8-P3 — **the cone hypothesis is demanded of capabilities the residual cannot use, and is refuted by one of them**

`Severity.v:341` (`cap_cone`) and `Interleave.v:620–621` (`strips_cap_cone`) both quantify over
**all** `a`. `reach_cone` only ever applies the hypothesis at capabilities occurring in `G`.

```coq
Definition tbl0 (a : CapN) : Cap :=            (* cap 0: what the residual uses  *)
  match a with                                  (* cap 1: a tool it never mentions *)
  | 0 => {| c_pre := fun _ => True;      c_vars := [];  c_add := [8]; c_del := [] |}
  | _ => {| c_pre := fun W => W 5 = 1;   c_vars := [5]; c_add := []; c_del := [] |}
  end.
Definition V7 := fun x => x = 7.  Definition Haz7 := fun W => W 7 = 1.
Definition Gres : Gt := GAct 0 0 GEnd.

Theorem strips_cone_hypothesis_fails : ~ (forall a x, In x (c_vars (tbl0 a)) -> V7 x).
Theorem cap_cone_hypothesis_fails :
  ~ (forall a W1 W2 W1', agree V7 W1 W2 -> Es tbl0 a W1 W1' ->
       exists W2', Es tbl0 a W2 W2' /\ agree V7 W1' W2').
Theorem the_cone_conclusion_holds_anyway : forall b W1 W2,
  agree V7 W1 W2 ->
  (safeT (Es tbl0) Haz7 b Gres W1 <-> safeT (Es tbl0) Haz7 b Gres W2).
```

Both hypotheses fail; the conclusion holds. This is not a pathology: it is the shape of the
paper's own modular experiment. `TC_seq_interface` (`Severity.v:912`) composes $G_1$ and $G_2$
under **one** capability context `E`; the tool projects the interface onto
`relevant_atoms(segs[i+1:])` (`scripts/severity_eval.py:178–186`), i.e. onto what the *remaining*
segments read; and the earlier segments' capabilities have preconditions on their own atoms,
which the renaming puts outside that cone. So Table 2's projected column is licensed by a theorem
whose hypothesis its own construction refutes — unless the quantifier is restricted.

### R8-P4 — **the fix costs fifty lines, and I have written them**

```coq
Variable CA : CapN -> Prop.                       (* the residual's capabilities *)
Hypothesis cap_cone_res : forall a W1 W2 W1',
  CA a -> agree V W1 W2 -> E a W1 W1' -> exists W2', E a W2 W2' /\ agree V W1' W2'.
Fixpoint caps_in (G : Gt) : Prop := …             (* mirrors guards_in_cone *)

Theorem reach_cone_res  : forall b G W1 W2, guards_in_cone V G -> caps_in G ->
  agree V W1 W2 -> reach_haz E Haz b G W1 -> reach_haz E Haz b G W2.
Theorem safeT_cone_res  : forall b G W1 W2, guards_in_cone V G -> caps_in G ->
  agree V W1 W2 -> (safeT E Haz b G W1 <-> safeT E Haz b G W2).
Corollary interface_projection_res : …
```

`reach_cone`'s existing proof goes through with one extra conjunct threaded, exactly as
`guards_in_cone` is threaded. `strips_cap_cone` then discharges `cap_cone_res` from
`forall a, CA a -> footprint containment`, which is the condition the tool's cone construction
*does* establish. This converts "a property of the front end" into a checkable side condition —
which is what the paper says it wants (`main.tex:1069–1072`).

### R8-P5 — **R5-W3 survives: `repair_guard_anywhere` still cannot take the paper's runtime**

```coq
Definition Wodd : World := fun x => if Nat.eq_dec x aborted then 5 else 0.
Theorem E2_is_not_globally_validating : ~ (forall W, validates_ab E2 3 psi2 ab2 W).
```

Re-proved against `50a2522`. Combined with the authors' own `global_abort_is_idempotent`, the
off-root guard repair still needs a constant abort map and still has no witness in the artifact.
Adding my R5-P3 witness (`ab3 := fun _ => Wab`) to `check_repairs.v` is twenty lines and closes it.

### R8-P6 — **R5-W8 survives: the worked guard instance never runs the guarded branch**

```coq
Definition Wv : World := wupd W2 verified 1.
Theorem Gguarded_intended_branch_runs : forall k, safeT E2 Haz0 k (GAct 3 1 FastPath) Wv.
Theorem Gguarded_tolerant_at_a_verified_world : forall k, safeT E2 Haz0 k Gguarded Wv.
```

`Gguarded_is_k_tolerant` is proved at `W2`, where `psi2` fails, so the ok-branch obligation for
the guarded branch is `exfalso`. The half of the repair the paper sells as its advantage over
narrowing — *"keeping it available when it is intended"* — is covered only by the general
`repair_guard_exact_ab`. The two lemmas above close it and make the booking story complete in
both directions.

### R8-P7 — **the bridge is empty on every protocol in the benchmark**

```coq
Definition Gself : Gt :=                     (* a choice with no receiver *)
  GComm 0 0 [ (10, (fun _ : World => True), GEnd) ;
              (11, (fun _ : World => False), FastPath) ].

Theorem Gself_is_0_tolerant           : safeT E0 Haz0 0 Gself W0.
Theorem Gself_has_no_conforming_session : forall s W, ~ ctypes E0 Gself s W.
Theorem Gself_never_steps : forall s W G' s' W' r c, ~ hstep E0 Gself s W G' s' W' r c.
```

`safeT` never reads the roles of a choice; `CT_Comm` requires `p <> q` and `H_Comm_ok`/`H_Comm_dev`
require `s p = POut q …` **and** `s q = PIn p …`. So a self-choice is accepted by the condition,
has no conforming session, and takes no step at all. See **N1** for why that is not a hypothetical.

---

## (c) NEW weaknesses introduced or exposed this round

### N1 — **MAJOR. Section 7 is vacuous on all seventeen benchmark protocols, and the paper does not say so**

*Evidence:* probe R8-P7; `src/skillc/kernel.py:133–134`; `src/skillc/data/severity_corpus.json`;
`Bridge.v:59–70,86–…`; `main.tex:1166–1174`, Table 3.

Three facts, each checkable in a minute:

1. **No choice in the corpus names a receiver.** All 23 `choice` nodes across the 17 packs
   have keys `{branches, by}` (plus `guards`/`external` on four); none carries `to`. The
   kernel elaborator therefore takes `q = b.get("to", b["by"])` and emits `(choice r r …)` — a
   global type whose choice is `RComm r r`.
2. **Fourteen of the seventeen protocols contain no communication at all.** Only the three
   `booking_*` packs have a `msg` step (2, 2, 1 of them); the other fourteen have zero, and eleven
   declare a single role.
3. **A self-choice has no session.** R8-P7: `ctypes` rejects every session for it, and `hstep`
   cannot fire. So `bridge_run`, `bridge_every_configuration`, `bridge_prefix`,
   `budget_distributes`, `markers_are_met`, `progress`, `every_label_steps`, `swap_ctypes` and
   `bridge_interleaved` — the whole of §7 and §9's typing half — are statements about the empty
   set for every protocol the evaluation measures.

What *does* transfer is the condition: `safeT`, `reach_haz`, $\kstar$, the trichotomy, the
severity labels, `principal`, the cone, the repairs. Those are role-blind, and the differential
test and Table 3 are unaffected. But the paper's headline sentence — *"a session typed against a
$k$-tolerant protocol by the base discipline's conformance judgment is hazard-free on every run of
cost at most $k$"* (abstract) — is evidenced by the hand-built Coq instances (`Gbad`, `Ggood`,
`Gguarded`, `Ggoal`) and by nothing in the artifact. The multiparty content of a multiparty
session types paper is three variants of one example, none of which the tool's own elaborator
keeps the roles of.

I want to be precise about the severity of this: **no theorem is wrong**, and this is a scope
claim, not a soundness defect. But it is the same species of defect as the one §11 says withdrew
the predecessor — a premise satisfied for the wrong reason, here satisfied nowhere in the
artifact — and §1 now advertises that this paper hunts for exactly that. A PC member who runs
`grep -c '"to"' severity_corpus.json` will notice.

**Fix, cheap.** (i) Add `to` to the three `booking_*` choices (and, better, to the two
`release_with_*` ones), so the tool's own elaboration produces a two-party choice; roles do not
enter `reach_haz`, so no reported number changes — I checked the analyzer and the kernel both
ignore them for $\kstar$. (ii) Add one genuinely two-party protocol to the benchmark and mark the
column. (iii) Say in one sentence which results the benchmark exercises (the condition and the
repairs) and which it does not (conformance, the bridge, progress, bystanders), and point at the
Coq instances that do.

### N2 — **MAJOR (small). The cone theorems are hypothesised over $\Gamma$ and applied over a residual**

*Evidence:* probes R8-P3, R8-P4; `Severity.v:341,912`; `Interleave.v:620,643`;
`scripts/severity_eval.py:178–186`; `main.tex:1054–1072`, Table 2.

This is R5-W5 sharpened, and this round made it sharper by adding the STRIPS bridge with the same
quantifier. Because `TC_seq_interface` fixes one `E` for $G_1$ and $G_2$, and the tool's cone is
computed from the *remaining* segments while the earlier segments' capabilities read their own
renamed atoms, the hypothesis of `safeT_cone` and of `strips_safeT_cone` is refuted at $n \ge 2$
in the very experiment they license. R8-P4 shows the restricted hypothesis is sufficient and costs
about fifty lines. This is the highest-value *theory* change available.

### N3 — **MODERATE. Table 3's "(repair: guard)" row is not the guard repair, and the "(repair: reorder)" row is not the reorder repair**

*Evidence:* `severity_corpus.json` (`email_campaign_guarded`, `booking_reordered`);
`Repairs.v:545–551`; `main.tex:1204,1207,1228–1230`.

- `email_campaign_guarded`'s own provenance note reads *"Repair 1 (guard): review inserted before
  the choice."* The pack has no validation, no abort map and no $\psi$-guarded branch; both
  branches do the same `send`. It is a **hoist** of `review` above the choice.
- `booking_reordered`'s note reads *"validation moved before the choice"* — the same hoist. The
  mechanized `Greordered` (`Repairs.v:549`) is a different transformation: `FastFirst`
  (purchase; verify) is replaced by `SafePath` (verify; purchase) *inside* the branch, which is
  `thm:reorder`'s adjacent swap.

So of the three rows that carry *"Repairs restore tolerance: reordering, narrowing and guarding
each take a $0$-tolerant protocol to tolerance at every $k$"* (`:1228`), exactly one — `narrow` —
instantiates a mechanized repair. The other two instantiate a fifth transformation that the
metatheory does not have. And the transformation they do instantiate is precisely the one that
needs no abort world at all, so this round's new and welcome honesty about $E_4$ never reaches the
evaluation: nothing in Table 3 depends on the freeze because nothing in Table 3 is the guard
repair. Either relabel the two rows ("repair: hoist"), or add a `validate` capability with an
abort effect to `email_campaign_guarded` and score the row the theorem is about.

### N4 — **MODERATE. `thm:inhabited` claims more than `canon_conforms` proves**

*Evidence:* probe R8-P1; `Bridge.v:644–652,741–743`; `main.tex:743–762`.

*"Every two-role protocol is inhabited"* + *"Two side conditions are exactly the two places the
general case is harder"* against a Coq predicate with four conditions, one of which excludes every
protocol in which the second role chooses — including the benchmark's `order_fulfilment`. R8-P1
shows `canon` conforms for such a protocol anyway, so the honest statement is either "every
two-role protocol in which one fixed role drives every choice", or (better, and half a page of
Coq) relax `two_role` to `{p,q} = {0,1}` and keep the sentence.

### N5 — **MINOR. `STATEMENTS.md` — the artifact's "what Coq actually says" manifest — is stale**

Regenerating it with the shipped `scripts/dump_statements.py` changes exactly three entries: it
adds the missing `bridge_prefix`, and it replaces the **pre-fix** forms of
`MBad_takes_the_wrong_branch` (with the excluded-middle hypothesis and an existential cost) and
`bridge_every_configuration` (existential in the intermediate configuration) with the fixed ones.
Header count goes 138 → 139. A referee who reads the shipped manifest — which is the file the
paper offers as the answer to "does each result say what you say it says" — sees the two
statements this round fixed in their unfixed form. Re-run the script before the artifact goes out,
and add it to `make check` beside `check_paper_citations.py` (which does pass: 139 cited, all
defined, all audited).

### N6 — **MINOR. Under-stated results and audit residue**

1. `Gmiss_safe` at budget 0 only (R8-P2); three lines to the statement the prose makes.
2. `Print Assumptions idle` on a `Definition` (`check_repairs.v:19`) still pads the audited count,
   which the supplement line now quotes as "186 theorems". That 186 is the number of
   `Print Assumptions` calls, over a development of 366 declared `Theorem`/`Lemma`/`Corollary`s;
   it reads as the development's size and is not.
3. `Interleave.v:635` names a hypothesis with a Cyrillic `а` (`destruct HE as [_ [Hа _]]`). It
   compiles; an artifact evaluator grepping for `Ha` will not find it.
4. `hrun_split` is now used by nothing (`bridge_prefix` goes straight through
   `bridge_every_configuration`), though it is still cited at `main.tex:735` and audited. Harmless,
   but the composite claim "every configuration *of this run*" is still not a single theorem — it
   is `hrun_split` followed by `bridge_every_configuration`, which is what the old
   `bridge_every_configuration` was.

### N7 — carried, unfixed from R5

`safeR` is still not displayed and the abstract still bundles the layers (R5-W6); prefix closure is
still finite-layer-only while `thm:bridge-mu` and `thm:bystander` say "every run" (R5-W7.4);
`repair_guard_anywhere` still has no instance (R8-P5); the guard repair's worked instance still
never runs the guarded branch (R8-P6).

---

## (d) Score

**B — weak accept. Confidence 4/5.** Held from R5, not raised.

The case for holding rather than raising. The two things R5 said would decide the paper — the false
conservatism sentence in §8, and the undisclosed runtime assumption under the repairs — are both
fixed, and the second is fixed better than I asked: `E4` is published as a non-example with five
theorems and the paper now says *"a deployment that only errors the call does not get the
theorem"*, which is a sharper and more useful claim than the one it replaced. Assumption 1's
classical-content caveat, `principal_exists`'s missing hypothesis, the universal
`bridge_every_configuration`, and a cost-pinned *and* constructive `MBad_takes_the_wrong_branch`
are all clean. The development is axiom-free with no `Admitted`, every cited result is audited, and
the disclosure paragraphs (`:793–804`, `:1069–1072`, `:1110–1123`, `:1574–1582`, `:1602–1613`) are
now the most trustworthy prose in the paper. On metatheory alone this is A-track work.

The case for not raising. N1 is the reason. A paper whose title says *multiparty session types* and
whose central theorem is a bridge from a typing judgment to session runs should be able to point at
one protocol in its own evaluation to which that bridge applies, and it cannot: every choice in the
corpus elaborates to `RComm r r`, for which `ctypes` admits no session and `hstep` cannot fire
(R8-P7), and fourteen of the seventeen protocols contain no message at all. That is a claims-versus-
evidence gap of exactly the kind §1 now advertises this paper hunts for, and it is invisible in the
current text. N2 is the second reason: this round added a STRIPS bridge for the cone and gave it a
hypothesis that the paper's own modular experiment refutes, so the one column of Table 2 that
carries Finding 3 is still not covered by a theorem whose premises hold. N3 means the repair
evaluation measures a transformation the metatheory does not contain.

None of these is a wrong theorem and none needs new mathematics. N1 is a corpus edit plus a
sentence, N2 is fifty lines I have already written, N3 is a relabelling. If all three land I would
argue A in committee. If N1 is left as it is, I would expect at least one PC member to argue C on
the grounds that the multiparty framing is unevidenced, and I would not be able to answer them.

---

## (e) Remaining weaknesses, ranked by how much each moves a PC member

1. **N1** — §7 is vacuous on the whole benchmark; the bridge has no artifact-level instance. *(major)*
2. **N2** — the cone hypothesis is over $\Gamma$ where the application is over the residual; refuted in the paper's own composition setting; fix in R8-P4. *(major, small)*
3. **N3** — Table 3's guard and reorder rows instantiate a hoist, not the mechanized repairs. *(moderate)*
4. **N4** — `thm:inhabited` overstates `canon_conforms`; two side conditions stated, four present, and the omitted one excludes a benchmark protocol. *(moderate)*
5. **R5-W6 / N7** — `safeR`'s single rule never displayed; abstract bundles "syntax-directed", "survives recursion" and "composes against an interface". *(moderate)*
6. **N5** — `STATEMENTS.md` ships the pre-fix statements of the two results this round fixed. *(minor, embarrassing)*
7. **N6, N7 residue** — `Gmiss_safe` at budget 0 only; `repair_guard_anywhere` uninstantiated; guard instance never runs the guarded branch; no prefix-closure at the $\mu$ and interleaved layers; `Print Assumptions idle`; the Cyrillic identifier. *(minor; R8-P2, P5, P6 supply three of the six)*

---

## (f) The single highest-value remaining change

**Give the bridge one instance the artifact actually contains, and state its scope for the rest.**

Concretely, in this order:

1. Add `"to"` to the three `booking_*` choice nodes and the two `release_with_*` ones in
   `severity_corpus.json`. `kernel.py:133` already reads it (`q = b.get("to", b["by"])`); with it,
   those protocols elaborate to a two-party choice instead of a self-choice. No reported number
   moves — neither `reach_haz` nor `goal_reach` reads the roles — so this is free.
2. Add one protocol to the benchmark whose choice is a real $\mathsf p \to \mathsf q$ with a
   bystander, and say in the Table 3 caption which protocols are single-participant.
3. Add one sentence to §7: *the bridge, progress, budget distribution and the bystander theorems
   are about protocols with a genuine sender/receiver pair at each choice; the benchmark's
   single-role packs exercise the condition and the repairs, not the conformance layer, and the
   Coq instances (`Gbad_inhabited`, `Gguarded_inhabited`, `Ggoal_inhabited`,
   `two_role_bridge_nonvacuous`) are where the conformance layer is exercised.*

I pick this over N2, which is cheaper in lines, for the reason the paper itself supplies. §11 says
the predecessor was withdrawn when its own audit found a premise that could not be satisfied, and
§1 now says every theorem here is checked for vacuity. The round-3 audit asked "is `inert (ab W)`
satisfiable?" and the authors answered it superbly, with `E2` and then with `E4` as the
non-example. The question that audit still has not asked is the outer one: **for the protocols we
actually measure, is `ctypes` satisfiable at all?** It is not — `p <> q` decides it in one line —
and the theorem chain that makes this a session-types paper rather than a planning paper is
therefore evidenced only by hand-built examples. A discipline whose stated methodology is to hunt
for premises that hold for the wrong reason should find this one itself, in print, and it will
cost the paper nothing to fix: the corpus edit is mechanical and the numbers do not move.

*Second-best, and I would take it in the same pass:* land R8-P4. Restricting the capability
bisimulation to the residual's capabilities turns Table 2's projected column from "a property of
the front end" into a theorem whose hypothesis the tool's cone construction establishes, and it is
fifty lines that already compile.

---

### Reproduction

Seven probe files, seventeen results, all `Closed under the global context`:

```
coqc -Q proof "" R8_P1.v   # two_role fixes the direction of every choice; canon conforms anyway
                  R8_P2.v   # Gmiss is safe at EVERY budget, not only at 0
                  R8_P3.v   # both cone hypotheses fail on a capability the residual never uses
                  R8_P4.v   # the restricted cone theorem, proved (~50 lines)
                  R8_P5.v   # E2 is still not globally validating
                  R8_P6.v   # the guard repair's missing intended-branch lemma
                  R8_P7.v   # a self-choice: safeT accepts it, ctypes and hstep reject it
```

Plus, outside Coq:

```
python3 scripts/dump_statements.py && git diff proof/STATEMENTS.md   # N5: 38 changed lines
python3 scripts/check_paper_citations.py                            # passes: 139 cited, all audited
python3 /tmp/n1.py                                                  # N1, script below
```

```python
# /tmp/n1.py -- no choice in the corpus names a receiver, and 14 of 17 packs
# contain no communication at all
import json
d = json.load(open('src/skillc/data/severity_corpus.json'))
def choices(steps):
    for s in steps:
        if 'choice' in s:
            yield s['choice']
            for b in s['choice']['branches'].values(): yield from choices(b)
        if 'rec' in s: yield from choices(s['rec'].get('body', []))
def msgs(steps):
    n = 0
    for s in steps:
        if 'msg' in s: n += 1
        if 'choice' in s:
            for b in s['choice']['branches'].values(): n += msgs(b)
        if 'rec' in s: n += msgs(s['rec'].get('body', []))
    return n
ch = [c for p in d for c in choices(p['pack']['protocol'])]
print('choices:', len(ch), 'with a "to":', sum('to' in c for c in ch))
print('packs with no msg step:', sum(msgs(p['pack']['protocol']) == 0 for p in d), 'of', len(d))
# -> choices: 23 with a "to": 0
# -> packs with no msg step: 14 of 17
```

Coq 8.18.0, stdlib only, run against the shipped `.vo`. No file in `proof/` and no line of
`main.tex` was modified; `STATEMENTS.md` was regenerated to a scratch copy and restored, and
nothing was committed.
