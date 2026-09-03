# ECOOP review — R16 (confirmation)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member. R13, R14 and R15 each found and fixed something. The pattern this review
history keeps producing is that a round's own fixes introduce the next round's findings, so this
round does nothing but try to break what those three rounds changed, plus the whole-artifact
verification from scratch.

**Version reviewed.** `main.tex` md5 `50b2dcf6…`. Working tree clean at start and at end.

## Verification, all from scratch

- **Paper.** Auxiliary files deleted, three full `pdflatex` passes: 28 pages, **0 errors, 0
  overfull boxes, no non-font warnings**, body ending page 25 with the conclusion intact,
  References opening 26.
- **Rendered output.** The PDF's text scanned for `??`, `[?]`, raw control sequences, TODO
  markers, draft markers and author placeholders in the body: **0 suspicious spots**.
- **Mechanization.** All ten `Print Assumptions` harnesses re-run: 12 + 2 + 36 + 35 + 10 + 27 +
  29 + 17 + 15 + 6 = **189**, every one `Closed under the global context`, **no `Axioms:` line,
  no errors** — matching `\supplement`'s "187 theorems and 2 constructors".
- **Numbers and citations.** 69 pinned numbers agree with `results/`; 144 cited Coq names all
  defined and all covered by a harness.
- **Tests.** 409 passed, 5 skipped.

## Trying to break the last three rounds

- **R15's proportional tolerance** applies to exactly eight claims — the seven wall-clock timings
  and the grep baseline's — and to nothing else; the other 61 are still exact. It accepts every
  drift the regeneration produced and rejects a 13.3\,ms figure becoming 40. Both directions
  re-checked.
- **R15's restore.** `results/` is byte-identical to what it was before the regeneration; the
  recorded evaluation was put back, not replaced.
- **An unexpected confirmation.** The regenerated `token_economics.json` came back with
  `wasted_usd` = 14.296 and `wasted_runs` = 46 — independently re-deriving the two figures R12
  had briefly and wrongly "corrected", from a clean run of the pipeline.
- **R14's page-budget compressions** were diffed against the originals in R15 and again here. No
  disclosure is missing; TRAC keeps both monitor kinds; reinforcement-learning safety is spelled
  out.
- **R13's added hypothesis** reads correctly in place and the theorem still fits its paragraph.
- **The verbatim block** still matches the tool byte for byte — the test that checks it passes.

## One thing, and it is mine

The README line R15 added said the regeneration takes "about ten minutes". The measurement was
about eight. Corrected to what was measured, because a README that rounds its own timing up is a
poor advertisement for a paper about not overstating numbers.

## Verdict

**Score: A (accept), confidence 5/5.** Nothing outstanding. Every check that can be run without
spending model tokens is green, from a clean tree, and the three preceding rounds' changes survive
adversarial re-reading. The one correction this round is to a sentence written in the previous one,
about the paper's own build instructions.
