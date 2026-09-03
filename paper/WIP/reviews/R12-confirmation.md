# ECOOP review — R12 (confirmation round)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member as R9/R10/R11. R11 returned **A, 5/5, nothing blocking**, with four
outstanding items and one standing observation: *four of the five findings two rounds ago were
introduced by the previous round's fixes.* This round checks the four fixes that answered R11
(commit `7117bdb`), then re-reads the paper for anything no round has looked at.

**Version reviewed.** Started at `7117bdb`, ended at `84291e5`; `main.tex` md5 `8cf8e857…`,
`main.pdf` 28 pages, body ending on 25 with References opening 26, 0 errors, 0 overfull boxes, no
non-font warnings.

**Mechanization, re-verified from the compiled development.** Ten `Print Assumptions` harnesses,
re-run this round: 12 + 2 + 36 + 35 + 10 + 27 + 29 + 17 + 15 + 6 = **189** lines, every one
`Closed under the global context`; no `Axioms:` line anywhere, no errors. That is the paper's
"187 theorems and 2 constructors" exactly. `STATEMENTS.md` regenerates with no diff.

## The four R11 fixes: all four land

1. The anti-monotonicity pointer. `main.tex:1278` now names `tolerance_antitone_in_ctx` and
   \S\ref{sec:typing}; the statement is at line 699–703, inside that section. Correct.
2. "That last condition." `strips_cap_cone` concludes `cap_in_cone`, the third and last
   hypothesis of Theorem 25. Correct.
3. The README's 67/68 sentence. 64 + 3 = 67 verified, 64 + 3 + 1 = 68 runs. Correct.
4. The `cite` mechanism. **Verified by perturbation, not by reading**: changing "6 of the 19" in
   `main.tex` fails the run with exit 1 and names the claim. It does what the commit says.

## What this round found

**F1 — the manifest guarded six phrases and not the four it was built for.** The turn medians
(7.5, 20.5), the tail (six runs of 65–127 turns) and the certified maximum (13) are the numbers an
earlier round caught being deleted on a false premise, and none was pinned. Pinned now.

**F2 — the guard was brittle and could crash.** `cite` matched literal bytes including newlines,
so re-wrapping a paragraph failed a correct paper; a guard that cries wolf gets loosened. Matching
is now whitespace-insensitive. A `cite` naming a missing file raised a traceback rather than
reporting a failure; it is its own failure class now. A test copies the tree, breaks a cited phrase
without touching any computed number, and requires rejection.

**F3 — Section 2's transcript was not the tool's output.** The paper prints seventeen lines and
says "the tool's output is what an engineer needs". The tool had gained a branch line
(`keep_old  Futile  misselection`, omitted entirely), a corrected branch count (6, not 5) and the
bystander summary Section 10 promises it reports. A reviewer running the artifact would have found
this in a minute. Replaced byte for byte; a test now diffs the CLI against the block.

**F4 — two figures nothing had checked.** $14.296 and the certified realistic-scale row. The
second was a truncation of exactly $1.645 and now rounds up. **The first was right and I broke
it**: I re-derived it from `usefulness.json` and got $14.297, when the paper reads
`token_economics.json`'s recorded `wasted_usd`. Restored, and the manifest entry now reads the
field the paper reads. The sentence around it summed three of the table's four refuted rows without
saying so; it names them now (46 of the 66).

**F5 — the tables were unchecked as tables.** Table 1 is 17 rows × 6 figures, Table 3 is 6 × 6,
Table 4 is 7 × 7 — about 150 numbers the manifest does not reach. All three now have row-by-row
tests, each verified to fail on a perturbed cell. Every cell of all three is correct against the
results. (Table 3's first column is the *complete* enumeration and the plain whole-system run
appears three lines above it in the prose; reading the wrong field makes a correct table look
broken.)

**F6 — source hygiene.** The file still opened with "NOT FOR SUBMISSION" and a grep-able
DO-NOT-SUBMIT marker whose conditions were cleared rounds ago, and pointed the mechanized audit at
Section 9 — which has been "Why a Discipline, and Not a Model Checker" since Section 12 folded into
Related Work. 46 of the preamble's 73 macros were the vocabulary of the refuted predecessor design
and were never used. Both cleared; the PDF is unchanged. The README's pre-submission list asked for
work already done and omitted `make check`.

**F7 — one ambiguity.** "Both repairs are exercised end to end", read after the compensate theorem,
names the wrong two. It is guard and reorder.

## What I read and did not fault

Introduction and C1–C5 (every claim traced to a named result); \S4's default guard instantiation;
\S5's trichotomy, Assumption 3's honest statement of its classical content, and the \Rob{}/\Ben{}
separation; \S7's non-vacuity construction and the marker's price stated as plainly as its benefit;
\S8's guardedness-is-necessary and the note that the decision procedure needs no such hypothesis;
\S9's cone of influence restricted to a residual's own tools; \S10 end to end — every cross-total
recomputed (28 runs = 12 + 16, $1.09, 1.56 M; 66 refuted; 20 of 66; 25 = 16 + 9; 34 = 16 + 18;
162 = 17 + 145; 32 = 162 − 130); \S11's aborting model, its non-example $E_4$, and the congruence's
stated price; \S13's limitations, which concede the benchmark's authorship, the single-rater audit,
the unretained discarded runs and the untested false-certification rate.

## Verdict

**Score: A (accept), confidence 5/5.** Nothing blocking. Seven findings, all cosmetic, provenance
or hygiene — none touches a theorem, a proof or a claim. The pattern R11 named held once more: one
of this round's own findings (F4) was a correct number I damaged and had to restore, which is why
every fix this round ships with a test that was verified to fail before it was kept.
