# ECOOP review — R9 (final PC read)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Program-committee member giving the final read before the committee meeting. Two
referees have reviewed across four rounds — R7 (evaluation and presentation, round 3, **B**) and
R8 (theory and mechanization, round 4, **B**) — and this is the version that answers both. I read
the whole paper as a referee would, and I re-derived every load-bearing claim from the artifact
rather than from the response.

**Version reviewed.** HEAD `d242022` ("Carry this round's admissions into Limitations"),
`main.tex` md5 `00350f2f…`, `main.pdf` 28 pages. **The tree moved under me during the review**
(`fc73c67` → `d242022`); I re-verified every finding below against `d242022` before writing. This
is the fourth consecutive round in which the reviewed artifact changed mid-review, and R7 has now
asked twice for a frozen submission. It is time to freeze it.

**Method.** Rebuilt the entire Coq development from source in a scratch copy
(`coqc -Q . ""`, nine files, ~11 s wall — the whole thing, not just the leaves); ran all ten
`Print Assumptions` harnesses and read every line of their output; wrote and compiled one new
probe file (**R9-P1**, four results, all `Closed under the global context`); regenerated
`STATEMENTS.md` and diffed it; ran `make check`, the full `pytest` suite, and the extracted kernel
against all seventeen benchmark protocols; re-derived Table 1 row by row from the corpus through
the shipped analyzer; re-derived Table 2 cell by cell, Finding 4's branch counts, the turn medians
and tail, the census aggregates and the hand audit, from `paper/WIP/results/`. Nothing in the
repository was modified: the probe file was removed and `git status` is clean.

---

## (a) Verdict

**B — weak accept. Confidence 4/5.**

I would argue for acceptance **with mandatory revisions**, and I would argue **A** if the five
items in §(e) land. I will not argue A as the paper stands, for one reason: the version submitted
to this round again states numbers that its own shipped artifact contradicts, and this time the
defect was *introduced by the commit that fixed the previous round's blocking finding*. That is
the fourth round running. Everything else about this submission is now in very good shape.

**What I verified as fixed, against the artifact and not the prose.** Both referees' blocking
items are closed, most of them properly:

| item | claimed | my verdict | evidence |
|---|---|---|---|
| **R8-N1** bridge vacuous on the whole benchmark | eight choices in six multi-role protocols name a recipient; no verdict moves; scope stated | **FIXED, and substantively so — but see F2** | 23 choices across 17 packs; 8 in 6 multi-role packs carry a `to` distinct from `by` (my census). Re-running the shipped analyzer over the corpus reproduces **all 17 rows exactly** — $k^*$, counts, branch totals, PNR, witness, narrowing, configs, goal queries — 0 mismatches, 55 branches, 29/7/19, $9\times0$ / $2\times1$ / $6\times{\ge}5$. The `severity.json` diff for that commit touches only `time_s`/`elapsed_s`. My probe **R9-P1** proves in Coq that the elaborated shapes of `booking_fastpath` (= `Gbad`) and `release_with_audit` satisfy `two_role`, hence `canon_conforms` gives each a conforming session on any total runtime: the bridge now has artifact-level instances, which is exactly what R8 asked for. §10's new scope paragraph (`:1205–1226`) is well written and says the right thing. |
| **R8-N2** cone hypothesised over $\Gamma$, applied to a residual | `cap_in_cone` per-capability, theorems take `uses U G` | **FIXED, exactly as R8-P4 prescribed** | `Severity.v:345–353` defines `cap_in_cone` per capability and `uses U G` structurally; `reach_cone`, `safeT_cone`, `interface_projection` all take `(forall a, U a -> cap_in_cone a)` and `uses U G` (`:393,418,432`). `strips_cap_cone`/`strips_safeT_cone` (`Interleave.v:620,639`) inherit the restricted form, and the condition is precisely "every *precondition* of an **invoked** tool reads only $V$" — which is what the tool's `relevant_atoms(segs[i+1:])` establishes by construction. The theorem now covers the experiment that uses it. This was the highest-value theory change available and it landed. |
| **R8-N3** Table 3's guard/reorder rows are hoists | both relabelled; the swap theorem's side condition stated | **FIXED, and better than asked** | Table 1 rows now read `(repair: hoist)`. The paragraph at `:1227–1240` says hoisting is `SW_comm`/`SW_comm_rev` only when the actor is uninvolved, "in both of these instances the actor *is* one of the communicating pair, so no theorem of ours licenses the transformation". I checked `SW_comm` (`Interleave.v:61–64`): it requires `r <> p -> r <> q`. And I checked both instances: `booking_reordered` hoists `verify@q` above a choice `p→q`, `email_campaign_guarded` hoists `review@agent` above a choice by `agent`. The disclosure is exactly right. |
| **R8-N4** `thm:inhabited` claims more than `canon_conforms` proves | four side conditions listed, two real, two convenience | **FIXED as disclosure** (not by relaxing `two_role`) — **and it interacts with F2** | `:759–768` lists all four and correctly separates the two real ones (distinct labels, no markers) from the two conveniences. `two_role` still demands `p = 0 /\ q = 1` at every choice (`Bridge.v:644–652`). |
| **R8-N5/N6** residue | STATEMENTS.md regenerated; `Gmiss_safe` at every budget; Cyrillic fixed; `Print Assumptions idle` removed; `safeR` displayed | **FIXED — one with a new hole, F5** | `python3 scripts/dump_statements.py` produces **zero diff** (141 results, header matches). `Gmiss_safe : forall b, safeT E0 Haz0 b Gmiss W0`. No non-ASCII anywhere in `proof/*.v`. `Print Assumptions idle` is gone. `safeR` is displayed as **T-Safe-$\nu$** at `:979–989` and it is *faithful* to `SR_step` (`Mu.v:545–550`), double line and all. |
| **R7-N1** withdraw-then-assert ordering | contradiction removed | **FIXED** | `grep` finds one surviving occurrence, `:1841`, and it reads "establishes non-vacuity **only**". |
| **R7-N2** "16 of those documents" | eight corpus skills + eight specification cases | **FIXED** | Abstract `:186` and C5 both say it. I resolved all 16 `skill` values in `usefulness_runs.jsonl` against the two `PROVENANCE.json` files: exactly 8 match the corpus, exactly 8 are `benchmarks/spec-cases/*`. `make check` now certifies the split, not just the cardinality. |
| **R7-N3** Table 1 caption 0.33 s vs prose 0.26 s | caption fixed | **FIXED** | Both now say 0.21 s; $\sum$`elapsed_s` over the 17 benchmark rows is **0.2081**. |
| **R7-N4** two medians deleted on a false premise | restored, with the tail | **FIXED, better than asked** | 7.5 (n=20) and 20.5 (n=18) reproduce from the 38 records carrying `size`; the paper now also prints the tail ("six of the 18 refuted runs ran 65 to 127 turns … against a maximum of 13 in the certified runtime") and all four numbers are in `CLAIMS.json`. The refuted distribution is `3,6,9,11,13,13,14,14,20,21,21,24,65,86,113,122,126,127`. Exact. |
| **R7-N5** "the models are not tracking risk" | inference withdrawn | **FIXED** | `:1379–1387` now says 10 of the 11 are the single \Ben{} detour "whose pressure prompt asserts exactly [its guard]— an agent taking it is arguably reading the guard correctly, not ignoring risk", and concludes "not enough to say anything about rates". This is the honest paragraph R7 asked for. (One residue: it still prints the two-class pair $11/120$ vs $2/180$ without the third class, $5/40 = 12.5\%$ at $k^*{=}1$, which reverses it. No inference now rests on it, so it is a nit.) |
| **R7-m5/m7/m8** | realistic-size qualifier, `cumulative`, hash-test floor | **ALL FIXED** | "(ten of them at realistic input size, six at the smaller one)", verified by `make check`; `differential.json.cumulative` is now 500/500 over two entries; `test_corpus_security.py:117` asserts `total == 162`. |
| **`make check`** | 43 numbers, 141 citations | **PASSES, and I re-ran it** | "all 43 checkable numbers agree with the shipped results"; "141 Coq results cited … all defined, all covered by a `Print Assumptions` harness". |

**And the mechanization itself.** I rebuilt all nine `.v` files from source: clean. No `Axiom`, no
`Admitted`, no `admit`. All ten harnesses run and **every one of the 189 lines of output is
`Closed under the global context`** — I read them, I did not count them. I spot-checked the
elaborated statements of `bridge_run`, `bridge_prefix`, `budget_distributes`, `progress`,
`every_label_steps`, `bridge_interleaved`, `swap_ctypes`, `markers_are_met` and `canon_conforms`
in `STATEMENTS.md` against what the paper claims for each: all faithful, including
`bridge_run`'s three-part conclusion and `budget_distributes`' `covers`/`NoDup` hypotheses. This
is the most trustworthy Coq artifact I have refereed in some time, and `STATEMENTS.md` plus
`check_paper_citations.py` is a practice I would like to see other submissions copy.

**And the evaluation.** Beyond what `make check` covers, I independently reproduced: Table 1 in
full; every counter cell of Table 2 (8/26/62/134/278/566 complete, 3/6/12/24/48/96 exits,
8/29/81/205/493/1149 concrete with 3/8/20/48/112/256 interface, 8/16/24/32/40/48 projected with
interface 2 throughout) — **exact**; Finding 4's "6 of the 19 \Cat{} verdicts taken 17 times,
1 of the 7 \Fut{} once, the one \Ben{} misselection taken 10 times" — **exact**; the census
149/13/108/95, 130/49/32, 80.2%, 2133.9 ms, 22 440 tokens, 27.9%, 15.84 M / \$14.296, 20 of 66;
the hand audit 6 genuine / 7 misextraction = 4.3% of 162 and 46% precision. The full test suite is
**404 passed, 5 skipped**. And I re-ran the extracted kernel against the corpus after the `to`
edit: **16 agree, 0 disagree, 1 skipped** (`order_fulfilment`, environment choice), max 19.6 ms —
so the paper's "agrees on every one, in under 50 ms each" survives the corpus change.

That is a large amount of verified, self-corrected work. The rest of this review is what is left.

---

## (b) The probe

`R9_P1.v`, compiled with `coqc -Q . ""` against the shipped `.vo`; all results
`Closed under the global context`. It asks the question R8-N1's fix invites but does not itself
answer: *now that the choices name recipients, is the bridge actually non-empty on the benchmark?*

```coq
Require Import Severity Bridge.

(* booking_fastpath's elaborated shape IS Gbad: choice 0->1, safe = verify;purchase,
   fast = purchase.  release_with_audit: ops=0, auditor=1, choice 0->1, then
   log@1 ; smoke@0 in both branches. *)
Definition Rtail : Gt := GAct 5 1 (GAct 6 0 GEnd).
Definition Grelease : Gt :=
  GComm 0 1 [ (1, (fun _ : World => True), GAct 3 0 (GAct 4 0 Rtail)) ;
              (2, (fun _ : World => True), GAct 4 0 Rtail) ].

Theorem booking_fastpath_is_two_role   : two_role Gbad.
Theorem release_with_audit_is_two_role : two_role Grelease.
Theorem booking_inhabited : forall Ec, (forall a W, exists W', Ec a W W') ->
  forall W, ctypes Ec Gbad (sess_of Gbad) W.
Theorem release_inhabited : forall Ec, (forall a W, exists W', Ec a W W') ->
  forall W, ctypes Ec Grelease (sess_of Grelease) W.

(* order_fulfilment: agent and bank BOTH choose, so one choice runs 1 -> 0. *)
Definition Gbank : Gt :=
  GComm 1 0 [ (7, (fun _ : World => True), GAct 8 0 GEnd) ;
              (9, (fun _ : World => True), GAct 10 0 GEnd) ].
Definition Gorder : Gt :=
  GAct 0 0 (GComm 0 1 [ (1, (fun _ : World => True), GAct 2 0 Gbank) ;
                        (2, (fun _ : World => True), GAct 3 0 (GAct 2 0 Gbank)) ]).
Theorem order_fulfilment_is_outside_two_role : ~ two_role Gorder.
```

The first four are the good news and belong in the paper (thirty lines). The fifth is **F2**.

---

## (c) What I found that is new

### F1 — **BLOCKING (one afternoon). Finding 3 and Table 2's caption state seven machine timings that the shipped `severity.json` contradicts, and the commit that fixed R8-N1 is what made them stale.**

`826f062` re-ran `scripts/severity_eval.py` to pick up the corpus edit. Its message says "No
verdict moves … with only the total time shifting", and the authors duly updated Table 1's total
(0.33 → 0.21 s). They did not update the *other* place `severity_eval.py` writes times. The
modularity paragraph and Table 2's caption still carry the pre-826f062 run:

| paper | line | shipped `severity.json` |
|---|---|---|
| complete enumeration, migration $n{=}6$: **27.6 s** | `:1303` | **22.408 s** |
| projected modular, $n{=}6$: **0.11 s** | `:1303` | **0.0829 s** |
| re-check whole-system, $n{=}6$: **131 ms** | `:1310` | **109.2 ms** |
| re-check modular: **17 ms** | `:1312` | **13.3 ms** |
| caption, whole-system range: **15–131 ms** | `:1331` | 15.0 – **109.2** ms |
| caption, modular range: **16–19 ms** | `:1331` | **12.4 – 15.6** ms |
| caption, deploy $n{=}6$: **661 ms vs 62 ms** | `:1333` | **470.2 ms vs 39.5 ms** |

None of these seven values occurs anywhere in `results/` any more; I grepped. (They match the
record at `826f062~1` exactly, which is how I identified the cause.) Table 2's caption reports
*only* times, so the caption is stale end to end.

I want to be precise about severity. **No finding reverses**: the counters, which are what the
argument rests on and which the paper explicitly says are the reproducible half ("we report the
counters, which reproduce exactly"), are exact in all 36 cells. The ratio that carries Finding 3
even improves, from 251× to 270×. This is bookkeeping, not science.

But it is the same bookkeeping defect the last three rounds have been about, it is in the section
those rounds cleaned, and it sits in precisely the gap R7's **m10** predicted: `CLAIMS.json` covers
43 numbers of roughly a hundred, and *not one* of the modularity timings is among them. R7 wrote
"the two errors this round that a manifest would have caught are exactly in the uncovered part";
this round the manifest again did not catch the error in the uncovered part. A PC member who does
what I did — open `severity.json` next to Table 2 — finds this in ninety seconds, and after four
rounds of "every number now comes from the shipped data" that is a bad look for an otherwise
scrupulous paper.

**Fix.** Update the seven numbers, and add the four modularity timings to `CLAIMS.json` so this
cannot recur. Two lines each.

### F2 — **MODERATE. "Apply to the six" is five: `order_fulfilment` is outside the bridge on two independent counts, and one of them is the side condition §7 calls "convenience".**

`:1213`: *"the bridge, progress, budget distribution and the bystander results are about sessions
and apply to the six."* `:1840` (Limitations) repeats it. Five of the six are fine — I proved two
of them in R9-P1 and the other three are the same shapes. The sixth is not:

1. **Two of `order_fulfilment`'s three choices are environment-controlled.** Definition~5's own
   closing sentence says *"the mechanization covers only participant-controlled choice, so no
   theorem in this paper is stated for it"*, and the kernel refuses the pack outright
   (`NotBoolean("environment choice")` — I reproduced the skip). Table 1 even labels the row
   "(environment choice)".
2. **Both role directions occur.** `agent` chooses towards `bank` and `bank` chooses towards
   `agent`. `two_role` requires `p = 0 /\ q = 1` at *every* choice (`Bridge.v:648`), so whichever
   way the two roles are indexed, one of the two choices violates it — this is
   assignment-independent. `canon_conforms` therefore gives `order_fulfilment` no session, and no
   other theorem in the paper does either. (R9-P1's fifth result.)

So the sentence written to close R8-N1 repeats R8-N1's error at one-sixth scale, and it does so
across the very side condition §7 introduces two pages earlier and dismisses as "convenience …
stronger than the proof needs". R8 flagged that this condition excludes `order_fulfilment` by
name; the paper answered by *disclosing* the condition and then, in the evaluation, quietly
counting the protocol it excludes.

**Fix, cheapest first.** (i) Say "five" and name the exception in the same clause — one word and a
parenthesis, and the honesty is then complete. (ii) Better, and what R8 asked for: relax
`two_role` to `{p,q} = {0,1}` with a symmetric case split in `canon_other`. R8 estimated half a
page of Coq; having now read `canon_conforms`, I agree — the direction is used only in
`canon_other`'s bookkeeping. That closes both F2 and R8-N4 and lets the theorem keep the sentence
it wants.

### F3 — **MODERATE. The artifact README contradicts the paper, including on a claim the paper explicitly withdraws.**

`paper/WIP/README.md` is what an artifact-evaluation committee opens first, and `make check` does
not look at it. Its "Evaluation headline" section is stale in at least six places, two of them
badly:

- *"catastrophes 0/120 on k\*≥5 vs 7/220 on k\*≤1 (one-sided Fisher p = 0.046, not conventionally
  significant)"* — this is the ordering claim the paper **withdrew** at `:1372–1378` on the ground
  that 0/120 is arithmetically forced and the scripted chooser reproduces it. The README presents
  it as a headline with a p-value.
- *"Differential testing: … agree … for 499 of 499"* — the paper says 500 of 500 and explains the
  499 as a generator bug, since fixed.
- *"Severity benchmark (… 0.33 s)"* — data says 0.208 s; the paper says 0.21 s.
- *"Corpus census (… 1.8 s)"* — paper says 2.1 s; data says 2133.9 ms.
- *"median compaction 22440 tokens = 31.2% of one agent run"* — paper and data say 27.9%.
- *"Modularity: whole-system complete 35.8 s at n=6 vs 0.13 s modular … concrete interface 2.9 s …
  Re-check 172 ms vs 22 ms"* — data says 22.4 s / 0.083 s / 1.875 s / 109.2 ms / 13.3 ms. These
  are stale by *two* regenerations, i.e. they do not even match the stale numbers in F1.

R7 credited `84f0d29` for fixing two stale README counts; it has drifted again. Either regenerate
the headline section from `results/` or delete it and point at `CLAIMS.json`.

### F4 — **MODERATE (venue). The paper is over the page limit.**

28 pages; the body runs to line 27 of 55 on page 26, so roughly **25.5 pages excluding
references** against ECOOP's 25. At R7 (round 3) it was 27 pages with about a quarter-page of
slack; §10 has since grown from 468 to **494 lines** while being compressed for the third time.
This is a desk-rejection risk and it is not something the committee can fix. R7's **P1/P3** say
where the space is: §10's 77-line preamble before Finding 1, and the 38% of §10 spent on the
off-thesis experiments (Finding 5, the grep paragraph, security, Finding 6).

### F5 — **MINOR, but pointed. "189 theorems" is 187, and the test written last night to prevent exactly this does not catch the two that slipped in the commit before it.**

`fc73c67` removed `Print Assumptions idle` — a `Definition` that padded the audited count — and
added `test_every_audited_name_is_a_proof_not_a_definition` to keep it from recurring. Good. But
the *previous* commit, `a2e9ef1`, added `Print Assumptions SW_comm` and
`Print Assumptions SW_comm_rev` to `check_interleave.v`. Those are **constructors of the inductive
`swap1`**, not proofs; `Print Assumptions` on a constructor prints "Closed under the global
context" for the same empty reason a `Definition` does. The new test's regex looks for
`^\s*(Definition|Fixpoint|Record|Inductive|CoInductive)\s+<name>` and a constructor is written
`| SW_comm :`, so it passes.

I classified all 189 audited names: **187 proofs, 0 definitions, 2 constructors.** The supplement
line should say 187, and the test should add the constructor pattern — which the citation checker
and `dump_statements.py` already contain, from that same commit. (Citing the constructors is
correct and I would keep it; only the counting and the auditing are wrong.) Separately, R8's point
that "189 theorems" reads as the development's size still stands: the development declares **373**
`Theorem`/`Lemma`/`Corollary`s, of which 187 are audited and 141 cited. One clause fixes it.

### F6 — **MINOR. "Eighteen tests" is nineteen.**

`:1107`. `826f062` added `test_multi_role_benchmark_choices_name_a_recipient` to
`tests/test_severity.py`, which now has 19. One could argue the new test checks the corpus rather
than "the tool's verdicts against the Coq development's", in which case the sentence needs
rewording rather than renumbering — but as written it is the file's test count, and it was.

---

## (d) Carried, unfixed, and worth one line each

These are all things a previous referee raised and the authors did not take. None is a blocker;
together they are the difference between B and A for a fussy reader.

1. **The worked guard instance still never runs the guarded branch** (R5-W8, R8-P6). `Abort.v:168`
   proves `Gguarded_is_k_tolerant` at `W2`, the all-zero world, where `psi2 W2` is false — so the
   intended-branch obligation is discharged by `exfalso` at line 173. The half of the repair the
   paper sells as its advantage over narrowing, *keeping the branch available when it is
   intended*, has no worked instance. R8-P6 supplies it in 25 lines and I would take them.
2. **`repair_guard_anywhere` still has no instance** (R5-W3, R8-P5), and by the authors' own
   `global_abort_is_idempotent` cannot have `E2` as one. The paper discloses this two lines after
   claiming "All four repairs therefore apply at nested positions", which is the right order but
   the wrong emphasis.
3. **`strips_safeT_cone` has no instance either.** The theorem is now the right theorem (F-fix
   R8-N2), but nothing in `proof/` discharges its syntactic hypothesis for a concrete table, and
   the one concrete cone instance (`V0`/`U0`, `Bridge.v:1015–1075`) proves `cap_in_cone` for
   *every* capability (`intros a _`) over a runtime whose tools have no preconditions — so it
   would go through under the old, refuted quantifier too. R8's carried request for an instance
   where $V$ is a proper subset *and* some capability has a non-trivial precondition is still
   open, and it is the instance that would show the restriction earning its keep.
4. **Prefix closure is still finite-layer only** (R5-W7.4, R8-N7). `bridge_prefix` exists and is
   strong; `bridge_mu` and `bridge_interleaved` conclude `~ Haz W'` at the endpoint while
   `thm:bridge-mu` and `thm:bystander` say "hazard-free on every run". ~8 lines each.
5. **The abstract still says "One syntax-directed rule characterizes the condition exactly."** The
   fix for R8's Moderate 6 — displaying `safeR` — has made this *worse*, not better: the newly
   displayed **T-Safe-$\nu$** is introduced as "one clause, **over the protocol's own steps rather
   than its syntax**". So the abstract's singular, syntax-directed rule now has two referents, one
   of which the paper itself says is not syntax-directed. The same sentence still bundles
   "composes against an interface … and is decidable for regular protocols", where `thm:seq` is
   explicitly finite-fragment-only. Two commas fix both.
6. **No interval estimates anywhere** (R7-M1). §10 contains exactly one inferential statistic
   (Fisher $p = 0.0025$). Rates like 0/18, 19/20, 32/32, 6/13 carry real weight in Finding 5 and
   none has an interval; the clustering unit (the seven catastrophes sit in two of sixty-eight
   cells) is still unstated. Wilson intervals cost one line each — but see F4, they cost a
   matching cut.
7. **The five discarded prompt-v1 runs are still in no shipped file** (R7-M2). The paper now says
   so in its own voice — *"the discarded runs were not retained, so a reader cannot audit that
   revision, which is a fault in our record keeping"* — which is the right disclosure and does not
   replace the five JSON lines.
8. **The 16-of-17 "pre-stated expectation" is still not independently dated** (R7-M4). The `note`
   fields, including the amended `order_fulfilment` one, are in `severity_corpus.json` at
   `fffda39`, committed with the tool. Limitations says "authored by us"; it does not say
   "undated".
9. **Table debts** (R7-P4, P6): Table 3's `$0.5` in a column of three-decimal costs (`$0.503` in
   the data); `20 (by hand)` as a value in a column of counts; the header "no verdict" where the
   prose says "without the status line the harness asks for"; Table 1's `loops` column zero in 16
   of 17 rows. And Table 2's caption still files the deploy family's *complete-vs-projected* times
   under a *re-check* heading — a defect R7 raised as P6 and which F1 has now compounded by making
   the numbers stale as well.
10. **The Finding 5 sentence at `:1442–1446` still does not parse on one pass** (R7-P5).

---

## (e) What would move me to A

In this order, and I think all five are under a day's work:

1. **F1** — update the seven modularity timings and put them in `CLAIMS.json`. *(the one thing I
   would ask for)*
2. **F2** — "five", not "six", with `order_fulfilment` named; or relax `two_role` and keep "six".
3. **F3** — regenerate or delete the artifact README's headline section; the withdrawn
   ordering claim must not survive there.
4. **F4** — get the body under 25 pages. §10's preamble and its off-thesis half are where the
   space is.
5. **F5/F6** — 187, not 189; the constructor pattern in the new test; nineteen tests.

If I were arguing this in committee I would say: the theory is A-track and the mechanization is
better than A-track — axiom-free, rebuilt from source in eleven seconds, 187 audited results with
every cited statement published and checkable, non-vacuity treated as a first-class obligation
with published non-examples (`E4`, `Gmiss`, `narrowing_breaks_conformance`), and a disclosure
discipline in §7, §8, §9 and §12 that I would hold up as a model. The evaluation is honest to a
degree that is rare: the grep-baseline paragraph gives away most of the credit for the corpus
census, the scripted-chooser floor is printed next to the number it deflates, the withdrawn
ordering claim is withdrawn in the authors' own words, and the new scope paragraph at `:1205`
tells the reader exactly which theorems the benchmark does and does not exercise. The story is
legible in one pass and the thesis — *session types say what may happen; this says what you can
survive* — is carried by the results rather than asserted over them.

What holds me at B is that after four rounds of correction the submitted version still contains
numbers its own artifact refutes, in the section that has been corrected three times, introduced
by the fix for the last round's blocking finding, in the region the previous referee explicitly
warned was unprotected. The fixes are trivial. The pattern is not, and I would want to see the
frozen, self-consistent version before I argued for acceptance rather than argued against
rejection.

**Score: B (weak accept), confidence 4/5.** Accept with mandatory revisions F1–F5; A if they land.

---

## Appendix — reproduction

Everything below was run from the repository root at `d242022`. Nothing was modified; the probe
file was removed afterwards and `git status` is clean.

```bash
# the whole development, from source, in a scratch copy
cp paper/WIP/proof/*.v $SCRATCH/ && cd $SCRATCH
for f in DeviationLayer Severity Regular Bridge Mu Repairs Abort Interleave Kernel; do
  coqc -Q . "" $f.v; done          # all nine OK, ~11 s total

# every audited result, read not counted
cd paper/WIP/proof
for f in check_*.v; do coqc -Q . "" $f; done
#  -> 17+35+2+12+15+6+27+10+29+36 = 189 lines, every one
#     "Closed under the global context", nothing else printed

# the probe (F2, and the good news about F2's five siblings)
coqc -Q . "" R9_P1.v                # 3 Print Assumptions, all closed

# the manifest is current
python3 scripts/dump_statements.py && git diff --stat paper/WIP/proof/STATEMENTS.md   # empty

# the checkers
make check          # 43/43 numbers; 141 citations, all defined and audited
python3 -m pytest tests/ -q          # 404 passed, 5 skipped
```

```python
# R8-N1, re-checked: 8 of 23 choices name a distinct recipient, in 6 of 17 packs
import json
d = json.load(open('src/skillc/data/severity_corpus.json'))
def ch(steps):
    for s in steps:
        if 'choice' in s:
            yield s['choice']
            for b in s['choice']['branches'].values(): yield from ch(b)
        if 'rec' in s: yield from ch(s['rec'].get('body', []))
named = sum(1 for p in d for c in ch(p['pack']['protocol'])
            if c.get('to') and c['to'] != c['by'])
# -> 8 named, of 23 total; 6 packs have >1 role

# no verdict moved: re-derive all 17 rows through the shipped analyzer
import sys; sys.path.insert(0, 'src')
from skillc.severity import analyze
ship = {r['id']: r for r in json.load(open('paper/WIP/results/severity.json'))['rows']
        if r.get('set') == 'severity_benchmark'}
for e in d:
    g = analyze(e['pack'], kmax=4).to_dict(); s = ship[e['id']]
    assert (g['tolerance_degree'], g['counts'], g['branches'], g['pnr_action'],
            g['configs_explored'], g['goal_queries']) == \
           (s['k_star'], s['counts'], s['branches'], s['pnr_action'],
            s['configs'], s['goal_queries'])
# -> 0 mismatches; 55 branches, 29/7/19; k* 9x0, 2x1, 6x>=5

# F1: the seven stale timings
m = json.load(open('paper/WIP/results/severity.json'))['modularity']
r = [x for x in m if x['family'] == 'migration' and x['n'] == 6][0]
print(r['whole_system_complete']['time_s'],    # 22.408  (paper: 27.6)
      r['modular_projected']['time_s'],        # 0.0829  (paper: 0.11)
      r['recheck_whole_system']['time_s'],     # 0.1092  (paper: 131 ms)
      r['recheck_modular']['time_s'])          # 0.0133  (paper: 17 ms)
# recheck ranges over n=1..6: whole 15.0-109.2 ms (caption: 15-131);
#                             modular 12.4-15.6 ms (caption: 16-19)
# deploy n=6: complete 470.2 ms vs projected 39.5 ms (caption: 661 vs 62)
# and: git show 826f062~1:paper/WIP/results/severity.json  <- where the paper's numbers came from

# F5: what the 189 audited names actually are
import re, pathlib
proof = pathlib.Path('paper/WIP/proof')
names = [n for f in sorted(proof.glob('check_*.v'))
         for n in re.findall(r'Print Assumptions\s+([A-Za-z0-9_\']+)\s*\.', f.read_text())]
src = "\n".join(f.read_text() for f in sorted(proof.glob('*.v'))
                if not f.stem.startswith('check_'))
ctor = [n for n in names if re.search(rf"^\s*\|\s*{re.escape(n)}\s*:", src, re.M)]
# -> 189 names: 187 proofs, 0 definitions, 2 CONSTRUCTORS ['SW_comm', 'SW_comm_rev']
# and: grep -cE '^\s*(Theorem|Lemma|Corollary|Proposition|Fact|Remark)\s' paper/WIP/proof/*.v  -> 373
```

```bash
# kernel agreement survives the corpus edit
# 16 agree, 0 disagree, 1 skipped (order_fulfilment: environment choice), max 19.6 ms

# F4: the page budget
pdfinfo paper/WIP/main.pdf | grep Pages            # 28
pdftotext -layout -f 26 -l 26 paper/WIP/main.pdf - # body ends at line 27 of 55; ~25.5pp body
```

Coq 8.18.0, stdlib only. `main.tex`, every `.v` file and every script are untouched;
`STATEMENTS.md` was regenerated to compare and restored with `git checkout`; nothing was
committed.
