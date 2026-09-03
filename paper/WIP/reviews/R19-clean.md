# ECOOP review — R19 (nothing found)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member, eighth reading. R18 was the first round the paper itself came through
unchanged; its two findings were in shipped documentation. This round re-reads what R18 changed,
finishes the last unswept corner of the artifact, and re-verifies everything from a clean tree.

**Version reviewed.** `main.tex` md5 `9bf966e7…`, unchanged since R17.

## The one thing this round found, and it is already fixed

`docs/LIVE_AGENTS.md` printed a section headed "Catastrophe rate by tolerance class" whose last
row is 0.0 for `k*>=5`. The paper withdrew exactly that inference in an earlier round, because
the zero is arithmetically forced: those six protocols have one choice point each and tolerate at
least four misselections, and the scripted chooser with no model in the loop reproduces 0/120. The
table is data and stays; the reason is now stated under it, in the generator so a re-run keeps it
and in the shipped report so it is true without re-running an experiment that costs model calls.

## Swept and clean

- **The four other generated reports** (`SEVERITY_RESULTS`, `TOKEN_ECONOMICS`,
  `SEMANTIC_VALIDATION`, `REAL_SKILLS_REPORT`) contain no interpretive prose at all — no
  "shows that", "demonstrates", "confirms". They are tables, and their aggregates agree with
  `results/`.
- **`docs/USEFULNESS.md`**, re-checked: 66 refuted and 68 certified runs, 64 successes and 1
  silent wrong certified, \$15.59 refuted spend, checker 227.9\,ms — all matching the paper.
- **R18's two fixes** read correctly in place: the spec-case README now attributes 0.2\,ms to the
  grep and 228\,ms to the checker, and `AUDIT.md` names the superseded draft it audits.
- **The caveat added this round** is byte-identical in the generator and the shipped report, so a
  regeneration cannot silently drop it.

## Whole-artifact verification, from a clean tree

- **Paper.** Auxiliary files deleted, three `pdflatex` passes: 28 pages, **0 errors, 0 overfull
  boxes, 0 non-font warnings**, body ending 25, References opening 26.
- **Numbers and citations.** `make check` exit **0**: 72 numbers agree with `results/`, every
  quoted phrase still present, 144 Coq names all defined and all covered by a harness.
- **Tests.** `pytest` exit **0**: 409 passed, 5 skipped.
- **Mechanization.** No `.v` file has changed since before R16's harness run: 189 names, every one
  `Closed under the global context`, no axioms, no admits.
- **Repository.** Working tree clean but for build products; `HEAD` equal to
  `origin/gc/paper-WIP`.

## Verdict

**Score: A (accept), confidence 5/5.** The paper needed no change for the second round running.
Eight rounds have taken it from "B, A if F1–F5 land" to a state where the findings are a caveat on
a data table in a generated report. I have nothing further.
