# ECOOP review — R18 (the artifact as a reader meets it)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member. R17 found the figure and the security wording by reading the parts the
text points at rather than the text. This round finishes that sweep: every document the paper cites
or ships beside itself, read against the paper.

**Version reviewed.** `main.tex` md5 `9bf966e7…`.

## Findings

**F1 — `benchmarks/spec-cases/README.md` gave the checker the grep's stopwatch.** "the checker
scores 34 of 34 in 0.2\,ms". The 0.2\,ms is the grep baseline's time over the 34 configurations;
the checker takes 228\,ms, as the paper and its table caption say. The document an evaluator opens
to understand the specification cases made the checker look a thousand times faster than it is.

**F2 — `proof/AUDIT.md` said it audits `main.tex`.** It audits the draft `main.tex` used to
be. "encodes the definitions of `paper/WIP/main.tex` as literally as possible and then tries to
prove the theorem statements" was true when written and false after the reframing — and the paper
points a reader at this file precisely to show its predecessor was refuted. It now names the draft
it audits and says why it is kept.

## Checked clean

- **The specification corpus** matches Section 10 exactly: nine pairs, eighteen `SKILL.md`
  variants on disk (9 A, 9 B), and the failure modes split 3 stated bounds / 3 blocked guards /
  2 missing establishers / 1 undeclared tool — the paper's "three bounds \ldots{} three guards
  \ldots{} two goal conditions \ldots{} one undeclared tool".
- **The hand audit** holds 13 entries, 6 genuine and 7 misextractions, which is what Section 10
  reports and what the manifest now checks.
- **`docs/USEFULNESS.md`** (generated) agrees with `results/`: 66 refuted and 68 certified runs,
  64 successes and 1 silent wrong on the certified side, \$15.59 refuted spend, checker 227.9\,ms
  over all configurations. Its narrower "success" column is not the paper's "verified", which the
  table caption already distinguishes.
- **`docs/CORPUS_SECURITY.md`** agrees with the corrected Section 10 sentence, from both
  directions: nine flags, the same two worth stating, neither among the sixteen executed.
- **Every path the paper names** — 17 across `scripts/`, `docs/`, `benchmarks/` and
  `proof/` — exists.

## Whole-artifact verification

Clean rebuild, auxiliary files deleted, three passes: **28 pages, 0 errors, 0 overfull boxes, 0
non-font warnings**, body ending page 25, References opening 26. `make check` exit 0 — **72
numbers, 144 citations**. `pytest` exit 0 — **409 passed, 5 skipped**. Coq unchanged since before
R16's harness run: **189 names, all closed under the global context, no axioms**.

## Verdict

**Score: A (accept), confidence 5/5.** Two findings, both in shipped documentation rather than the
paper, both fixed. The paper itself came through this round without a change, which is the first
time that has happened.
