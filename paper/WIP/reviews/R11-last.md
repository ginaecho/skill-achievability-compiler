# ECOOP review — R11 (last read)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member as R9 (**B**, "A if F1–F5 land") and R10 (**A**, 4/5, with two must-fix
items N1/N2 and trimming damage N3/N4). This read does three things: verify the six claimed
changes against the artifact rather than the response; hunt specifically for damage *introduced by
this round's edits*, since four of R9's five findings were introduced by the previous round's fixes;
and read the paper once more end to end as a referee.

**Version reviewed.** HEAD `a4c0a0b` ("Two wrong statements, and the hedges the page-budget trim
took with it"), `main.tex` md5 `7dcbce5a…`, `main.pdf` 28 pages, working tree clean at the start of
the review and clean at the end. The tree did not move under me. Second round running.

**Scope of the change.** `git diff 83a2e8d a4c0a0b` touches `main.tex` (5 hunks), `README.md` (1
hunk), `results/CLAIMS.json` (+3 entries), plus build products and the R10 review file.
`git diff 83a2e8d a4c0a0b -- paper/WIP/proof/ scripts/ src/ tests/ Makefile` is **empty**. I did not
take that on trust: I re-copied the nine `.v` files into a scratch tree and rebuilt the whole
development from source (`coqc -Q . ""`, **11.9 s**), then ran all ten `Print Assumptions` harnesses
and read the output — **189 lines, every one `Closed under the global context`, nothing else
printed**. No `Axiom`, no `Admitted`, no `admit` (the two grep hits are the word "Axiom-freeness" in
a comment header). R9's and R10's assessment of the mechanization carries over verified, not
inherited.

---

## (a) Verdict

**A — accept. Confidence 5/5.**

All six claimed changes land, and I re-derived every one of them from the artifact. More
importantly for this submission: **this round's edits introduced nothing.** I looked hard, in the
three places the last two rounds taught me to look — numbers that now disagree, sentences broken by
a matching cut, and content the cuts removed — and found no defect of any of those kinds. That
pattern, which held for four consecutive rounds and was R10's only reason for holding a point back,
has cleared.

I have one genuine finding and it is not about a number: **the guard the authors added does not
guard what they say it guards** (§(c) W1). And I have one small defect that eleven rounds of review
have walked past (§(d) W4). Neither is a blocker; both are shepherd items.

---

## (b) The six claims, verified

| claim | verdict | evidence |
|---|---|---|
| **N1** "that middle condition" → "that last condition" (`:1078`) | **FIXED, and it is now the right pointer** | Theorem 31 lists three conditions in this order: the hazard reads only $V$; every guard of $G$ reads only $V$; every capability $G$ invokes maps $V$-agreeing worlds to $V$-agreeing successors. I checked the Coq: `strips_cap_cone` (`Interleave.v:620`) concludes `cap_in_cone Es V a` from `(forall x, In x (c_vars (tbl a)) -> V x)` — the **capability** hypothesis, third and last — and `strips_safeT_cone` discharges `safeT_cone`'s capability premise through it. The paper's "it suffices that every *precondition* of an invoked tool reads only $V$" is exactly `c_vars (tbl a)` via `pre_supported`. The same sentence's earlier "the last, restricted to $G$'s own tools" now agrees with it; the paragraph no longer calls one hypothesis two different ordinals. |
| **N2** README "64/68" → "67/68" with a breakdown | **FIXED, and the arithmetic is exact** | `README.md:150–152` now reads "certified 67/68 verified artifacts (64 also reached the status line, 3 verified without it, 1 was a silent wrong result)". Re-derived from `results/usefulness.json` row by row over the 17 certified configurations: 68 runs; $\sum$`success` = **64**; $\sum$`verified_no_status` = **3** (2 on `xlsx`, 1 on `docx`); $\sum$`silent_wrong` = **1** (`google-workspace-cli` at 500 users). 64+3 = 67 verified; 64+3+1 = 68. This now matches Table 3's certified rows (32/32, 16/16, 20/19) and the caption's definition of the column. |
| **N2** "the three numbers are in `CLAIMS.json`" | **THE ENTRIES EXIST; THE GUARD DOES NOT** | See **W1**. The three entries are there and `make check` grew 55 → **58**, all passing. But `check_paper_numbers.py` never opens `README.md`, and 67 and 68 appear **nowhere in `main.tex`** — I grepped both the source and the rendered PDF. |
| **N3** restore "and uses no inline markers" (`:804`) | **FIXED, and the claim is true** | Now: "Our benchmark carries the goal as a pack-level condition **and uses no inline markers**, so no measurement depends on this." Verified against `src/skillc/data/severity_corpus.json`: the string `marker` occurs **zero** times across all 17 packs, and nothing in `src/skillc/data/` matches it case-insensitively. The sentence again establishes its own premise, and it sits correctly after "which is also why Theorem 14's construction excludes markers". |
| **N4** restore the hand-computation hedge in Limitations | **FIXED** | `:1810`: "…which is the gate's design**;** at the sizes those skills are for that route closes (Finding~5), **but the verdict does not claim it always does**." The clause that keeps the paper's most extrapolation-prone empirical claim from reading as universal is back. |
| **N4** restore the `live_agents_runs.jsonl` filename | **FIXED** | `:1353`: "(\texttt{scripts/live\_agents.py}; every run is in \texttt{results/live\_agents\_runs.jsonl})". The file ships and is complete: **340 records** (= the 340 runs), $\sum$`agent_calls` = **400** (matching "400 agent decisions"; the raw `choices` lists total 420 because 20 are the environment's), $\sum$`cost_usd` = **\$1.5921** (paper "\$1.59"), fields `pack, model, cond, seed, choices, outcome, misselections, pnr, agent_calls, cost_usd`. An artifact evaluator no longer has to guess. |
| **page geometry** — body still ends on page 25 | **HOLDS** | `pdfinfo`: 28 pages. `pdftotext -layout -f 25 -l 25` ends with the Conclusion's last line at **line 55 of 55**; `-f 26 -l 26` opens "**References**" at the top of a page numbered 0:26. Body = 0:1–0:25 = **25 pages**, References 26–28, no appendix. In budget against ECOOP's 25 excluding references. |

**Re-run at the repo root, on this commit:**

- `make check` → "**all 58 checkable numbers agree with the shipped results**"; then "141 Coq results
  cited … all defined, all covered by a `Print Assumptions` harness". **Passes.**
- `python3 -m pytest tests/ -q` → **404 passed, 5 skipped**, 8.2 s.
- `python3 scripts/dump_statements.py` → `STATEMENTS.md`, **zero diff**.
- The whole Coq development rebuilt from source, nine files, **11.9 s**; ten harnesses,
  **189/189 `Closed under the global context`**.
- Re-derived Table 1 through the shipped analyzer: **17 rows, 0 mismatches**, 55 branches,
  29/7/19, $k^*$ 9×0, 2×1, 6×≥5.
- `git status` clean; `main.tex` md5 unchanged from the start of the review. Nothing was modified.

**Integrity of the edit itself.** `\coqok{}` set and `\ref{}` set are **byte-identical** to
`83a2e8d` (md5 of the sorted sets: same). 61 bibitems, all cited. Zero `\ref` without a `\label`,
zero `??` in the PDF, zero undefined-reference warnings, **zero overfull hboxes**; the only two
underfull hboxes are the same two as before at the same paragraphs (`main.log` diffs to nothing but
timestamps and line-number shifts).

---

## (c) What this round introduced

### W1 — **MINOR, but it is the one thing I would name at the meeting. The three new `CLAIMS.json` entries do not prevent the recurrence they were added to prevent.**

The claim accompanying this revision is: *"the three numbers are in `results/CLAIMS.json` so the
column mix-up cannot recur."* It can.

`scripts/check_paper_numbers.py` is a manifest evaluator: for each entry it computes a value from
`results/` and compares it to the entry's `"paper"` literal. Its own docstring says that literal is
"**the literal the paper prints**". It never opens `main.tex` and never opens `README.md`; nor does
`check_paper_citations.py`, which reads `main.tex` only for `\coqok{}` names. So:

- The new entries do **not** tie the README's text to the data. Change `67/68` back to `64/68` in
  `README.md` and `make check` still prints "all 58 checkable numbers agree" — in the file where the
  error was, and the file the artifact committee opens first.
- They do not tie `main.tex` to the data either, because **the paper does not print 67 or 68
  anywhere**. I grepped `main.tex` and the rendered PDF for `\b6[78]\b`: no match. Table 3 gives the
  certified rows as 32/32, 16/16 and 20/19, and the prose gives 32, 16 and 19; the aggregate 67 of
  68 exists only in the README.

So all three entries are data-against-data — the manifest asserts that
$\sum$`success` $+\sum$`verified_no_status` $=67$ and that $\sum$`runs` $=68$, both computed from the
same file, with no anchor in any prose a reader could have got wrong. `make check` grew by three
numbers and by no coverage. This extends R10's N6 (four entries recording the data value where the
paper prints a rounded one) from "slightly less load-bearing than it sounds" to "not load-bearing at
all" for this claim; and unlike N6's four, these two have no printed counterpart in the paper to be a
rounding of.

I want to be fair about severity. **The README's number is now correct** — I re-derived it — and the
fix the authors were asked for landed. This is an overclaim about a guard, not a wrong number, and it
is a defect in the *response*, not in the paper.

**Fix, and it is three lines.** The repo already contains exactly the right pattern:
`tests/test_proof.py:126–130` reads `main.tex` and asserts the literal
`"(187 theorems and 2 constructors"` appears in it, which is what made the F5 fix stick. Do the same
for the README — assert `"67/68 verified artifacts"` (and, since the README's parenthesis prints them,
`64` and `3`, which the manifest still does not cover) appears in `README.md`. Alternatively, give
`check_paper_numbers.py` an optional `"in"` field naming the file the literal must occur in, which
would close the gap for all 58 entries at once and would be the right long-term answer to R7's m10.

### W2 — **NIT. The README's new parenthesis reads as a decomposition of 67 and sums to 68.**

*"certified 67/68 verified artifacts (64 also reached the status line, 3 verified without it, 1 was a
silent wrong result)"*. The first two items decompose the **67**; the third accounts for the
remaining run of the **68**. On a careful read the "also" carries it, and every number is right. A
reader skimming adds 64+3+1 and gets 68 next to a printed 67. Recasting as "…67 of 68 (64 with the
status line, 3 without; the remaining run was a silent wrong result)" costs nothing.

### W3 — **NIT. One matching cut cost a comma the sentence wanted.**

`:1445`. Before: "*Where it is*, no refuted run succeeded. The three document skills produce binary
formats**,** and all 12 file-only runs failed honestly." After: "*Where it is*, no refuted run
succeeded**:** the three document skills produce binary formats and all 12 file-only runs failed
honestly." Two independent clauses are now joined by a bare "and" after a plural noun phrase, so
"produce binary formats and all 12 file-only runs…" garden-paths for a word. The colon is also doing
less work than it looks like it is: the claim it introduces ("no refuted run succeeded") ranges over
*two* groups, and the second — the four specification B variants — arrives in a new sentence outside
the colon, so the parallelism the two-sentence version had is gone. **Content is intact**: I checked
all of it against `usefulness.json` (3 document skills × 4 runs = 12, all `honest_fail`; spec B rows
12 honest + 2 silent wrong + 2 no-status = 16; 12+16 = 28 runs, \$1.087 and 1.557 M tokens against
the paper's "\$1.09 and 1.56 M"). Restore the comma, or restore the full stop.

### W4 — **OBSERVATION on the page budget. The "matching cuts" did not pay for anything; the restorations fit by luck of reflow, and there is still exactly zero slack.**

I diffed the rendered text of `83a2e8d`'s PDF against this one. Both are **28 pages and 1492 lines**,
and the normalized diff touches **46 lines, all inside the four edited paragraphs**. Nothing anywhere
else in the document moved by a single line. That is because the two cuts saved a comma and the
three characters of "and " → ";" — about forty characters *less* than the restorations added — and
the three paragraphs happened to re-break to the same line count (11 → 11, 8 → 8, and the Finding 4
hunk is a one-line substitution). No overfull box resulted, so the outcome is fine and the body is
genuinely 25 pages. But the authors should not believe they have demonstrated a budget-neutral edit
discipline: they got this one for free, and R10's N5 still stands unchanged — page 25 runs to line 55
of 55, and the next addition (a Wilson interval, the sandbox caveat, W2's rewording if it runs long)
needs a real cut.

### Also looked for, and did not find

- **No number now disagrees.** Beyond the 58 in `make check` I re-derived by hand: Table 1 in full
  through the shipped analyzer (17/17 exact); Table 3's every cell against `usefulness.json`
  (certified 32/16/20 with 32/16/19 verified; refuted 12/16/20/18 with 0/0/20/0 verified and
  0/2/0/5 silent wrong, aggregating to 66 runs, 20 verified, 7 fabrications, and the 46 runs where
  the procedure is the only route); the 28-run cost and token totals; the grep baseline's 25 vs 34
  and 16/16 + 9/18; Finding 4's 340/400/\$1.5921; and the census, compaction and modularity figures.
  All reproduce.
- **No sentence broken by a cut.** The Limitations paragraph and the marker paragraph both read
  correctly in context; I read them in the PDF, not the source, to be sure the line breaks did not
  hide anything.
- **Nothing load-bearing lost.** The only two cuts are the comma in W3 and an "and". No `\coqok`,
  no `\ref`, no bibitem, no disclosure.
- **The PDF is current with the source.** All five edits are present in the rendered text.
- **The mechanization is what R9 described**, re-verified from source rather than inherited.

---

## (d) Read as a referee: what is still weak

I said I would say plainly whether anything remains. It does — four things, all small, and one of
them has been sitting in the paper since `fffda39` and no referee has named it.

### W5 — **The one I would actually raise. A cross-reference points at the wrong theorem, in the same way N1 did.**

`:1278`, Finding 2's closing sentence:

> "The last pair refines **Theorem~\ref{thm:exact}**'s anti-monotonicity: for a *fixed* hazard more
> tools never help, but the derived hazard is not fixed — a tool that re-establishes a lost atom
> removes a point of no return."

`thm:exact` is **Theorem 10, Exact characterization** — $\vdash_k G,W \iff \neg (G,W)\rightsquigarrow^H_k$.
It says nothing about $\Gamma$ and has no monotonicity content of any kind. Anti-monotonicity is
`tolerance_antitone_in_ctx`, and it is stated in the **unnumbered** paragraph after Theorem 11
(`:700–703`, "Reachability is also monotone in $\Gamma$, so for a fixed hazard granting a tool can
only lower $k^*$"). A reader who follows the pointer lands on the exactness theorem and finds nothing
to refine.

This matters slightly more than a stray `\ref` because that sentence is doing real work: it is the
paper's own claim that the mechanization refuted a design expectation, promised in C1 (`:318`) and
paid off here. And the deeper problem is that there is no theorem to point at — the result is
prose-only, so `\ref` had nowhere correct to go. **Fix:** either number that paragraph (it deserves
it; the intro sells it as a refuted expectation) and point at it, or write "the anti-monotonicity of
§6 (\coqok{tolerance\_antitone\_in\_ctx})".

I checked every other `\ref` in the paper against its target — 37 references, `thm:strips`,
`thm:bystander`, `thm:bridge`, `thm:embed`, `thm:distribute`, `thm:mu-judgment`, `thm:decide`,
`thm:cands`, `thm:narrow`, `thm:guardabort`, `thm:guarded`, `thm:seq`, `thm:markers`,
`thm:inhabited`, `thm:principal`, `thm:cone`, `thm:product`, `thm:decide-mu`, all tables and figures.
`:1278` is the only one that misses. (`:1114`, "the tool's search is the graph form of
Theorem~\ref{thm:cands}", is loose — the search is the product graph of Theorem 21 *restricted to*
`cands` — but it is defensible and I would not raise it.)

### W6 — **Carried, and I would still buy it back if a cut is found.** R10's N4(2), the security
paragraph's deleted reproduction caveat: "a temporary working directory is not a jail, and the runs
are unattended by design." R10 marked it "consider" and the authors did not restore it; that is a
reasonable call under W4's zero slack. It is still the one sentence warning a re-runner of 162
third-party skills what they are re-running, and the paragraph it belongs to already discloses that
one corpus skill pipes a download into a shell and another appends an API key to a shell profile.
Eleven words. If anything comes out of §10, this goes back in first.

### Carried from R9 §(d) and R10 §(d), unchanged and unblocking

None of these moved; the source they live in is byte-identical to R10's. For the record: the worked
guard instance still never runs the guarded branch (R5-W8); `repair_guard_anywhere` and
`strips_safeT_cone` still have no concrete instances; prefix closure is finite-layer only; the
abstract's "One syntax-directed rule characterizes the condition exactly" still has two referents now
that **T-Safe-$\nu$** is displayed and described as "over the protocol's own steps rather than its
syntax"; no interval estimates anywhere; the five discarded prompt-v1 runs are in no shipped file;
the pre-stated expectations are undated; Table 3's `$0.5`, `20 (by hand)` and the "no verdict" header
stand; the Finding 5 sentence at `:1430–1435` ("For eight skills … and for four of those nine
pairs — the five added after the agent runs were checked statically only —") still does not parse on
one pass; and "187 theorems" still reads as the development's size when the development declares
**368** results, of which 187 are audited and 141 cited. The two "six"s in §10 (five of the six
multi-role protocols; the six $k^*\ge5$ protocols) still sit two paragraphs apart. And the supplement
line carrying "187 theorems and 2 constructors" is still invisible in the anonymous build.

---

## (e) The score

R10 held a point back for one reason, stated explicitly: after four rounds of correction, a fix had
again introduced or left a number the artifact contradicts, and R10 wanted to see one round in which
that did not happen. **This is that round.** I went looking for it specifically — every number in the
edited paragraphs and every number they cross-reference re-derived from `results/`, the rendered PDF
diffed line for line against the previous build, the Coq rebuilt from source rather than assumed —
and there is no wrong number, no broken sentence and nothing load-bearing removed. The two must-fix
items are fixed, the three restorations read correctly in context and are each *true* of the shipped
data, and the body is 25 pages with References opening clean on 26.

What is left is: a guard that guards less than its commit message says (W1), two nits (W2, W3), and
a wrong `\ref` that has survived eleven rounds (W5). That the sharpest thing I can find on a fifth
read is a cross-reference to Theorem 10 in a sentence about $\Gamma$-monotonicity is itself the
verdict on this submission.

I would argue for acceptance without hesitation. The theory is A-track; the mechanization —
axiom-free, rebuilt from source in twelve seconds, 189 audited results each printing `Closed under
the global context`, every cited statement published in `STATEMENTS.md` and checked by a script, with
non-vacuity treated as a first-class obligation and published non-examples (`E4`, `Gmiss`,
`narrowing_breaks_conformance`) — is better than A-track and is a practice I would hold up to other
submissions. The evaluation gives away credit it could have kept (the grep baseline, the scripted
chooser floor, the withdrawn ordering claim, the post-hoc partition flagged as post hoc, "the audit is
single-rater and ours"), and §10's scope paragraph tells the reader exactly which five of seventeen
protocols the session-level theorems reach.

**Score: A (accept), confidence 5/5.**

**For the shepherd, none blocking:**

1. **W5** — `:1278`, `Theorem~\ref{thm:exact}` is the wrong target for anti-monotonicity. Number the
   paragraph at `:700` or cite `\coqok{tolerance\_antitone\_in\_ctx}` and §6.
2. **W1** — make the README's `67/68` (and `64`/`3`) actually checked, in the style of
   `tests/test_proof.py:126`, or add an `"in"` field to `CLAIMS.json`. Do not say the mix-up "cannot
   recur" until one of those exists.
3. **W2/W3** — recast the README parenthesis; restore the comma at `:1445`.
4. **W6** — if any space is found in §10, the sandbox caveat goes back first.

---

## Appendix — reproduction

Run from the repository root at `a4c0a0b`. Nothing was modified; `git status` is clean and
`main.tex` md5 is `7dcbce5a997dcd62f6d2e55cdbb17847` before and after.

```bash
make check                                  # 58/58 numbers; 141 citations, all defined and audited
python3 -m pytest tests/ -q                 # 404 passed, 5 skipped
python3 scripts/dump_statements.py          # STATEMENTS.md: zero diff
git diff --stat 83a2e8d HEAD -- paper/WIP/proof/ scripts/ src/ tests/ Makefile   # empty

# the whole development, from source, in a scratch copy
cp paper/WIP/proof/*.v $SCRATCH/ && cd $SCRATCH
for f in DeviationLayer Severity Regular Bridge Mu Repairs Abort Interleave Kernel; do
  coqc -Q . "" $f.v; done                   # nine files, 11.9 s, no failures
for f in check_*.v; do coqc -Q . "" $f; done
#  -> 189 lines, every one "Closed under the global context", nothing else

# page geometry
pdfinfo paper/WIP/main.pdf | grep Pages                # 28
pdftotext -layout -f 25 -l 25 paper/WIP/main.pdf -     # Conclusion ends, line 55 of 55
pdftotext -layout -f 26 -l 26 paper/WIP/main.pdf -     # "References" at the top of 0:26

# nothing else in the document moved
git show 83a2e8d:paper/WIP/main.pdf > old.pdf
pdftotext -layout old.pdf old.txt; pdftotext -layout paper/WIP/main.pdf new.txt
wc -l old.txt new.txt                                  # 1492 and 1492
diff <(norm old.txt) <(norm new.txt) | grep -c '^[<>]' # 46, all inside the four edited paragraphs

# W1: nothing in `make check` reads the README, and the paper never prints 67 or 68
grep -n "README" scripts/check_paper_*.py              # no match
grep -nE '\b6[78]\b' paper/WIP/main.tex new.txt        # no match
```

```python
# N2, re-derived row by row
import json
rows = [r for r in json.load(open('paper/WIP/results/usefulness.json'))['rows']
        if r['checker'] == 'certified']
sum(r['runs'] for r in rows)                 # 68
sum(r['success'] for r in rows)              # 64   <- what the README used to print as "verified"
sum(r['verified_no_status'] for r in rows)   # 3
sum(r['silent_wrong'] for r in rows)         # 1
# 64 + 3 = 67 verified == Table 3's 32/32 + 16/16 + 20/19

# N3: the corpus really has no markers
json.dumps(json.load(open('src/skillc/data/severity_corpus.json'))).lower().count('marker')  # 0

# N4: the restored filename names a complete file
rs = [json.loads(l) for l in open('paper/WIP/results/live_agents_runs.jsonl')]
len(rs), sum(r['agent_calls'] for r in rs), round(sum(r['cost_usd'] for r in rs), 4)
# 340, 400, 1.5921   -- paper: 340 runs, 400 agent decisions, $1.59

# Table 1, re-derived through the shipped analyzer
# 17 rows, 0 mismatches; 55 branches; Benign 29 / Futile 7 / Catastrophic 19
```

```
# N1, in the Coq
Interleave.v:620  Theorem strips_cap_cone : forall (V : Var -> Prop) (a : CapN),
                    (forall x, In x (c_vars (tbl a)) -> V x) -> cap_in_cone Es V a.
# cap_in_cone is Theorem 31's THIRD and LAST hypothesis. "that last condition" is correct.
```

Coq 8.18.0, stdlib only. `main.tex`, every `.v` file and every script are untouched; the scratch
build tree was deleted; nothing was committed.
