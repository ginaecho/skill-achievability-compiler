# ECOOP review — R20 (nothing left to find)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member, ninth reading. The three previous rounds moved from the paper to the
artifact to the numbers behind both. This round asks the completeness question directly:
**is there a claim in this paper that nothing checks?**

**Version reviewed.** `main.tex` md5 `53789475…`.

## Method

Extracted every numeral in the body — stripping comments, the verbatim transcript, and structural
references — and asked, of each, whether the numbers manifest computes it, a table test checks it,
or it is a budget or a small ordinal. The answer at the start of the round was that **fifty were
unguarded**, among them the headlines of Findings 5 and 6.

## Findings, all closed

**F1 — the census headline was never checked against the file it comes from.** 149 certified at
home, 108 refuted in the file-only runtime, 95 flipping, 13 refuted at home; `autocheck`
escalating on 130 and on 49, free on 32; the compaction economics of 20 usable packs at a median
22\,440 tokens, \$0.088, and 27.9\% of a measured median agent run. Eleven numbers, all sitting
in `token_economics.json`, none pinned. All eleven now are.

**F2 — twelve more of the same kind.** The 400 agent decisions, the 170 plain runs, the 220 runs at
$\kstar\in\{0,1\}$, the 66 refuted runs, the 65-to-127 tail, the \$1.09 and 1.56\,M over the
28 document and specification-B runs, the census's 2.1\,s, the 4.3\% false-refutation rate, and
the two campaign sizes making up the 500. Pinned. The rate now divides the audit's own
misextraction count by the corpus size rather than carrying a hand-written 7, so it moves if the
audit does.

**F3 — the nine-and-nine coincidence.** "$\kstar$ distribution $9\times 0$ \ldots{}
point-of-no-return actions purchase, send, deploy, delete, ship, purge, refund, drop\_old, commit"
puts a nine-item list after a count of nine. The list is every distinct point of no return across
all seventeen protocols; the nine $0$-tolerant ones name seven of them. The sentence says which
now. The abstract's claim survived the check that prompted it: all nine $0$-tolerant protocols do
name a point-of-no-return action.

**F4 — the corpus arithmetic.** "162 skills from thirteen public repositories", "seventeen
\ldots{} and 145 more from twelve third-party collections". A directory count is not a results
file, so the manifest cannot reach it; a test does.

## What is left, and why

Four figures are unchecked, and the manifest's note now names them rather than leaving a reader to
discover the boundary: the 228\,ms and the kernel's 50\,ms, measured directly and recorded in no
results file; the Fisher p-value, a statistic over two pairs that are both pinned; and the 28
guard-holding branches, which come from the tool's per-branch output rather than its aggregate.

## Verification

- **104 checkable numbers** agree with `results/`, every quoted phrase still present, **144 Coq
  citations** all defined and covered. `make check` exit 0.
- **Not self-satisfying**: perturbing `certified_home` in the results to 148 fails the run and
  names the claim; perturbing "170" in the prose fails it and names the claim. Both directions.
- **409 tests** pass, 5 skipped, including cell-by-cell checks of all three tables.
- **Paper**: clean rebuild, 28 pages, 0 errors, 0 overfull boxes, 0 non-font warnings, body ending
  25, References opening 26.
- **Coq**: unchanged since before R16's harness run — 189 names, all closed under the global
  context, no axioms.

## Verdict

**Score: A (accept), confidence 5/5.** Every quantitative claim in the paper is now either derived
from a shipped file by an expression in the manifest, checked cell by cell by a test, or named in
the manifest as deliberately unchecked with the reason. I have no further findings.
