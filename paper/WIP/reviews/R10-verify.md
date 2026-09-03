# ECOOP review — R10 (verification of the R9 revision)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member as R9. R9 scored **B** and said "**A** if F1–F5 land". This read verifies
F1–F6 against the artifact, not against the response, and then looks for damage: numbers that now
disagree, broken cross-references, self-contradicting prose, and content lost in the page-budget
trimming.

**Version reviewed.** HEAD `83a2e8d` ("Land the five things the final read said stood between B and
A"), `main.tex` md5 `c6689e95…`, `main.pdf` 28 pages, working tree clean. The tree did **not** move
under me this time — the first round in five in which that is true.

**Scope of the change.** `83a2e8d` touches `main.tex`, `README.md`, `results/CLAIMS.json`,
`tests/test_proof.py`, and the build products. `git diff d242022 83a2e8d -- paper/WIP/proof/
scripts/ src/` is **empty**: no `.v` file, no script and no source file changed, so R9's
mechanization findings carry over unaltered. I re-ran `dump_statements.py` anyway — `STATEMENTS.md`
regenerates with zero diff.

---

## (a) Verdict

**A — accept. Confidence 4/5.**

F1–F6 all land, and I verified every one of them by re-deriving the numbers, not by reading the
prose. The mechanization is untouched and remains what R9 described. Two one-line defects remain
(§(c)); by my own stated criterion neither is a blocker, and I would send them to a shepherd rather
than hold the paper. I am at 4/5 rather than 5/5 for the reason given in §(e).

---

## (b) F1–F6, verified

| item | verdict | evidence |
|---|---|---|
| **F1** seven stale machine timings | **FIXED, all seven, and the gap is closed** | Re-derived every value from the shipped `results/severity.json`: migration $n{=}6$ complete enumeration **22.4077 s** (paper `:1298` "22.4 s"); projected modular **0.0829 s** (paper "0.083 s"); re-check whole-system **109.2 ms** (paper `:1305` "109 ms"); re-check modular **13.3 ms** (paper `:1307` "13 ms"); caption whole-system range over $n{=}1..6$ **15.0–109.2 ms** (caption "15–109 ms"); caption modular range **12.4–15.6 ms** (caption "12–16 ms"); deploy $n{=}6$ **470.2 ms vs 39.5 ms** (caption "470 ms vs 40 ms"). All seven agree. The counters are untouched and still exact (566 / 48 / 1149 / 256 / 22 / 7 / 8). The ratio the finding rests on is now $270.2\times$, up from the withdrawn 251×. |
| **F1** manifest gap | **CLOSED — twelve entries, and `make check` grew from 43 to 55** | `results/CLAIMS.json` gains exactly twelve modularity entries (6 counters, 6 timings). I ran `make check` at the repo root: **"all 55 checkable numbers agree with the shipped results"**, then "141 Coq results cited … all defined, all covered by a `Print Assumptions` harness". This was the one thing R9 asked for and it is done properly — the numbers are now computed out of `severity.json` by expression, not transcribed. |
| **F2** "apply to the six" | **FIXED, and both reasons are true** | `:1209` now reads "apply to five of the six — `order_fulfilment` is out twice over, since two of its choices are the environment's and its choices run in both directions between one pair." I re-derived from `severity_corpus.json`: `order_fulfilment` has 3 choices, **2 carry `external: true`**, and its direction set is $\{(\mathsf{agent},\mathsf{bank}),(\mathsf{bank},\mathsf{agent})\}$ — both directions between one pair, which `two_role`'s $p{=}0 \wedge q{=}1$ rules out under either indexing. It is the **only** pack of the six with either property: the other five have a single direction and no environment choice. Limitations (`:1813`) agrees — "only five of its seventeen protocols are in scope for the session-level results". Independently corroborated by the extracted kernel, which skips exactly that pack. |
| **F3** README contradicts the paper | **FIXED on all six named items — one unnamed seventh survives (§(c) N2)** | The withdrawn ordering claim **and its p-value are gone**, replaced by "**No rate claim is supported** — 0/120 … is arithmetically forced, the low-`k*` counts invert, and 10 of the 11 …". 499 → **500 of 500 across two seeds**. 0.33 s → **0.21 s** ($\sum$`elapsed_s` = 0.2081). 1.8 s → **2.1 s** (2133.9 ms). 31.2% → **27.9%**. The modularity line is regenerated and now matches `severity.json` exactly. Beyond the six: the trichotomy conflation is stated ("**over all branches** — 28 of the 29 Benign are branches whose guard holds, so restricted to *misselections* the split is 1/7/19") and so is the document split ("16 documents — 8 corpus skills and 8 specification cases"). |
| **F4** page budget | **FIXED** | `pdfinfo`: 28 pages. `pdftotext -f 25 -l 25` ends with the Conclusion's last line; `pdftotext -f 26 -l 26` begins "**References**" at the top of a page numbered 0:26. Body = pages 0:1–0:25 = **25 pages**, References 26–28, no appendix. Against ECOOP's 25 excluding references, this is in budget. |
| **F5** "189 theorems" | **FIXED, and the test now really guards it** | `:148` reads "Coq development (**187 theorems and 2 constructors**, axiom-free, Coq 8.18)". I re-classified all audited names myself: **189 = 187 proofs + 0 definitions + 2 constructors** (`SW_comm`, `SW_comm_rev`), no duplicates. `test_every_audited_name_is_a_proof_not_a_definition` now matches `^\s*\|\s*<name>\s*:` and asserts the literal string `"(187 theorems and 2 constructors"` appears in `main.tex` — so the count and the paper are now welded together. It passes. |
| **F6** "Eighteen tests" | **FIXED** | `:1104` reads "Nineteen tests"; `tests/test_severity.py` has exactly **19** top-level tests. |

**Re-run at the repo root, on this commit:**

- `make check` → 55/55 numbers, 141 citations, all defined and audited. **Passes.**
- `python3 -m pytest tests/ -q` → **404 passed, 5 skipped**, 8.8 s.
- `python3 scripts/dump_statements.py` → `STATEMENTS.md` unchanged.
- Extracted kernel against the corpus → **16 agree, 0 disagree, 1 skipped**
  (`order_fulfilment`, `NotBoolean("environment choice")`), **max 23.4 ms** — the paper's "agrees
  … on every one, in under 50 ms each" holds, and the skip is the same protocol F2 now excludes.
- `git status` clean; nothing in the repository was modified by this review.

**Live-agent re-derivation** (because Finding 4's prose was reflowed): 340 runs, 400 agent
decisions, **\$1.5921**; plain condition **0 misselections in 170 runs**; pressured 28; catastrophes
**7**, all pressured, 5 on `staged_commit` and 2 on `booking_fastpath`, small model only;
`staged_commit` pressured small model 5 of 5 with 3 misselections each. Every number in the reflowed
paragraph survives the reflow.

---

## (c) What the fixes introduced or left behind

### N1 — **MUST FIX (one word). Theorem 24 now points the reader at the wrong hypothesis.**

`:1076`. The cone theorem states three conditions: the hazard reads only $V$; every guard of $G$
reads only $V$; and every capability $G$ invokes maps $V$-agreeing worlds to $V$-agreeing
successors — the last of which the same sentence explicitly calls "**the last**, restricted to $G$'s
own tools". Four lines later the compressed text now says:

> "For \textsc{strips} capabilities **that middle condition** is a containment the tool can check"

It is not the middle condition. `strips_cap_cone` (`Interleave.v:620–621`) concludes `cap_in_cone`,
which is the **capability** hypothesis — the third and last. The pre-trim wording, "the capability
condition", was correct; the compression replaced a correct noun phrase with a wrong ordinal, and
the same paragraph now calls one hypothesis both "the last" and "that middle". A reader who follows
the pointer lands on "every guard of $G$ reads only $V$" and will not understand why a *precondition*
containment discharges it. This is in the theorem that was R8-N2's fix and this round's headline
theory change, so it is the worst place in the paper for it. **One word: "middle" → "last".**

### N2 — **MUST FIX (one number). The README still disagrees with the paper in a seventh place.**

`paper/WIP/README.md`, Evaluation headline: *"Usefulness (…): **certified 64/68 verified
artifacts**"*. The paper's Table 4 gives the certified rows as 32/32, 16/16 and 20/19 — **67 of 68**
— and its caption defines the column: "'Verified' counts artifacts that pass the verifier whether or
not the status line was reached." I reconciled it against `results/usefulness.json`:
`certified_runs` 68, `certified_success` **64**, `verified_no_status` **3**, so verified = 64 + 3 =
**67**. The README is quoting `certified_success` under the label "verified artifacts" — the exact
distinction the table's caption exists to draw.

In fairness: this line predates `83a2e8d` and R9 did not name it, so this is a survivor rather than
a regression, and it is one number in a README. But F3's stated fix was "it now says what the paper
says", and it does not, in the file the artifact committee opens first. **"64/68" → "67/68".**

### N3 — **MINOR. A trimmed sentence lost its premise and no longer follows.**

`:804`. Before: "Our benchmark carries the goal as a pack-level condition **and uses no inline
markers**, so no measurement depends on any of this." After: "Our benchmark carries the goal as a
pack-level condition, so no measurement depends on this." Carrying the goal at pack level does not by
itself entail the absence of inline markers, which is what the marker/conformance hazard needs. The
claim is *true* — I checked, `severity_corpus.json` contains no marker step of any kind, string
`marker` occurs zero times — but the sentence as trimmed does not establish it. Restore four words.

### N4 — **MINOR. Three disclosures went out with the page budget. I would buy two back.**

The trimming was, on the whole, well judged: it took redundancy and rhetoric, and it dropped **no
Coq citation** (I diffed the `\coqok{}` sets across the commit — identical) and **no
cross-reference** (I diffed the `\ref{}` sets — identical), and every one of the 61 bibitems is
still cited. But three cuts removed content rather than words:

1. **Limitations, the hand-computation hedge.** Was: "at the input sizes those skills are for, that
   route closes (Finding~5), **but the verdict does not claim it always does**". Now: "and at the
   sizes those skills are for that route closes (Finding~5)." The deleted clause is the hedge on the
   paper's most extrapolation-prone empirical claim, and deleting it *strengthens* the claim. Six
   words; I would put them back.
2. **The security paragraph's reproduction caveat.** Deleted: "a temporary working directory is not
   a jail, and the runs are unattended by design." No reviewer asked for this; the authors wrote it
   themselves, and it is the one sentence warning anyone who re-runs 162 third-party skills what
   they are re-running. (Reviewers *did* ask for this paragraph to shrink, so the instinct was
   right; this was the wrong sentence to spend.)
3. **The live-agent data pointer.** Was: "each run's protocol, model, condition, seed, choices,
   outcome, misselection count and cost are in `results/live_agents_runs.jsonl`". Now: "every run is
   in `results/`". The file is real and complete — I read all 340 records out of it — but the paper
   no longer names it, and an artifact evaluator now has to guess. Restore the filename at least.

Not restored, and I agree with dropping them: the TRAC mechanism recap (R3 and R6 both asked for
that section to shrink), the $\mu X.X$ note in Limitations (it is stated in full as
Theorem~\ref{thm:guarded} at `:1006–1020`, so nothing was lost), and the Conclusion's
contribution recap. The Conclusion is now three sentences and lands better than the list did.

### N5 — **OBSERVATION, not a defect. There is now zero slack.**

Page 25 runs to its last line (55 of 55). The body fits, but nothing further can be added — not a
Wilson interval, not the restored clauses in N4 — without a matching cut. §10 came down only 11
lines (494 → 483); most of the saving came from §7, §8, §12 and §13. If the committee asks for any
addition, it must say what comes out.

### N6 — **OBSERVATION on the manifest.** Four of the twelve new `CLAIMS.json` entries record the
*data* value where the paper prints a rounded one (109.2 / 13.3 / 470.2 / 39.5 against the paper's
109 / 13 / 470 / 40 ms), so for those four the check is data-against-data and the tie to the printed
prose is still by eye. The caption's two ranges (15–109, 12–16 ms) are covered only at the 109
endpoint. Not wrong — the rounding is honest in every case, I checked all four — but the manifest is
slightly less load-bearing than "twelve modularity numbers are in `CLAIMS.json`" suggests.

### Also checked, and clean

- **No dangling or orphaned references.** 55 labels, 37 referenced, zero `\ref` without a `\label`,
  zero `??` in the PDF, zero undefined-reference warnings and **zero overfull hboxes** in `main.log`.
- **The PDF is current** with the source: it contains "five of the six", "Nineteen tests", 22.4 s,
  0.083 s, 109 ms, 13 ms and the corrected caption.
- **No internal number now disagrees.** Table 1's caption (0.21 s), the census (2.1 s), the
  compaction figures (22 440 tokens, 27.9%), the totals (15.8 M, \$14.296), Table 4's rows and
  Finding 4's counts all still reproduce from `results/`; I re-derived Table 4's certified rows
  (32/32, 16/16, 20/19) and the refuted aggregate (20 of 66, 7 fabrications, 0 of 46) by hand.
- **"Five of the six" does not collide with the other "six".** `:1368`'s "each of those six
  protocols has a single choice point" is the six $\kstar\ge5$ protocols, a different set from the
  six multi-role ones. Both readings are locally clear; a reader skimming §10 could still trip.
  Pre-existing.
- **The supplement line is invisible in the submitted PDF.** LIPIcs' `anonymous` option replaces
  `\supplement{…}` with "Anonymous supplementary material", so "187 theorems and 2 constructors"
  never renders. Correct in the source and it will appear on de-anonymization; worth knowing that
  the F5 fix is not reader-visible in this build.

---

## (d) Carried from R9 §(d), still open

None of these changed, none is a blocker, and R9 did not list them as conditions. For the record:
the worked guard instance still never runs the guarded branch (R5-W8); `repair_guard_anywhere` and
`strips_safeT_cone` still have no instances; prefix closure is still finite-layer only; the
abstract's "One syntax-directed rule characterizes the condition exactly" still has two referents
now that **T-Safe-$\nu$** is displayed; no interval estimates anywhere; the five discarded prompt-v1
runs are still in no shipped file; the pre-stated expectations are still undated; Table 3's `$0.5`,
`20 (by hand)` and the "no verdict" header still stand; and the Finding 5 sentence at `:1425–1430`
("For eight skills … and for four of those nine pairs — the five added after the agent runs …")
still does not parse on one pass. R9's residual note that "187 theorems" reads as the development's
size also stands: the development declares **368** `Theorem`/`Lemma`/`Corollary`s, of which 187 are
audited and 141 cited. One clause would fix it.

---

## (e) The score, and why 4/5 and not 5/5

Everything R9 made a condition landed, and landed by re-derivation rather than assertion: the seven
timings are the shipped ones, the manifest now covers them so the class of error cannot recur
silently, the scope sentence names its exception and both of its reasons are true of the data, the
README's withdrawn claim is gone, the body is 25 pages with References starting clean on 26, and the
audited-name count is now guarded by a test that would have caught the constructors. `make check`
grew from 43 to 55 numbers. Nothing in the mechanization moved, so R9's assessment of it — axiom-free,
189 audited results all `Closed under the global context`, every cited statement published in
`STATEMENTS.md` — stands unchanged. This is the frozen, self-consistent version R9 asked to see, and
it is the first round in five in which the artifact did not move mid-review.

I hold one point back because the pattern that kept R9 at B has not fully cleared: a number in the
shipped artifact still disagrees with the paper (N2), in the same file F3 was about, after a rewrite
whose commit message says "It now says what the paper says". It is one number in a README rather
than seven in the evaluation, the direction of travel is unmistakable, and I did not name it in R9 —
so it would be unfair to block on it. But it is why I would want N1 and N2 confirmed fixed before
the camera-ready rather than taken on trust.

**Conditions for the camera-ready (shepherd, not blocking):**

1. **N1** — `:1076`, "that middle condition" → "that last condition" (or restore "the capability
   condition"). *One word, and it is in Theorem~24.*
2. **N2** — README, "certified 64/68 verified artifacts" → "67/68".
3. **N3** — `:804`, restore "and uses no inline markers".
4. **N4** — restore the hand-computation hedge in Limitations and the
   `live_agents_runs.jsonl` filename; consider the sandbox caveat in the security paragraph. Any of
   these costs a matching cut (N5).

**Score: A (accept), confidence 4/5.**

---

## Appendix — reproduction

Run from the repository root at `83a2e8d`. Nothing was modified; `git status` is clean.

```bash
make check                               # 55/55 numbers; 141 citations, all defined and audited
python3 -m pytest tests/ -q              # 404 passed, 5 skipped
python3 scripts/dump_statements.py       # STATEMENTS.md: zero diff
git diff --stat d242022 83a2e8d -- paper/WIP/proof/ scripts/ src/   # empty
pdfinfo paper/WIP/main.pdf | grep Pages                  # 28
pdftotext -layout -f 25 -l 25 paper/WIP/main.pdf -       # body ends, line 55 of 55
pdftotext -layout -f 26 -l 26 paper/WIP/main.pdf -       # "References" at the top of 0:26
```

```python
# F1: all seven, from the shipped record
import json
m = json.load(open('paper/WIP/results/severity.json'))['modularity']
mig = [r for r in m if r['family'] == 'migration']; dep = [r for r in m if r['family'] == 'deploy']
r6 = mig[-1]
r6['whole_system_complete']['time_s']   # 22.4077  paper 22.4
r6['modular_projected']['time_s']       # 0.0829   paper 0.083
r6['recheck_whole_system']['time_s']    # 0.1092   paper 109 ms
r6['recheck_modular']['time_s']         # 0.0133   paper 13 ms
[round(r['recheck_whole_system']['time_s']*1000,1) for r in mig]  # 15.0 .. 109.2  caption 15-109
[round(r['recheck_modular']['time_s']*1000,1)      for r in mig]  # 12.4 .. 15.6   caption 12-16
dep[-1]['whole_system_complete']['time_s'], dep[-1]['modular_projected']['time_s']  # 470.2 / 39.5 ms
r6['whole_system_complete']['time_s'] / r6['modular_projected']['time_s']           # 270.2x

# F2: order_fulfilment is the only pack with both directions, and the only one with env choices
d = json.load(open('src/skillc/data/severity_corpus.json'))
# booking_fastpath {('p','q')} ext 0 | booking_reordered {('p','q')} ext 0
# booking_narrowed  {('p','q')} ext 0 | release_with_audit {('ops','auditor')} ext 0
# release_with_cache {('ops','cache')} ext 0
# order_fulfilment  {('agent','bank'), ('bank','agent')} ext 2   <- out twice over
# 8 named choices across those 6 packs, of 23 total

# F5: what the 189 audited names are
# -> 187 proofs, 0 definitions, 2 constructors ['SW_comm','SW_comm_rev']; 368 declared results

# N2: the README's 64 is certified_success, not verified
u = json.load(open('paper/WIP/results/usefulness.json'))['aggregate']
u['certified_runs'], u['certified_success']          # 68, 64
# per-row: success 64 + verified_no_status 3 = 67 verified  == Table 4's 32/32 + 16/16 + 20/19
```

```python
# the extracted kernel, after the corpus and prose changes
# 16 agree, 0 disagree, 1 skipped (order_fulfilment: environment choice), max 23.4 ms

# integrity of the trimming
# \coqok{} set before vs after 83a2e8d: identical
# \ref{}   set before vs after 83a2e8d: identical
# 61 bibitems, 61 cited, 0 orphans, 0 missing; 0 overfull hboxes; no undefined references
```

Coq 8.18.0, stdlib only. `main.tex`, every `.v` file and every script are untouched; nothing was
committed.
