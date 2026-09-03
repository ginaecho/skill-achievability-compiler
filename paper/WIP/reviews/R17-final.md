# ECOOP review — R17 (the parts no round had read)

**Paper:** *Affordable Mistakes: Severity-Aware Multiparty Session Types for Participants that
Choose Wrongly*

**Role.** Same PC member. R16 was a confirmation round and turned up only a wording slip in its own
predecessor's README line. This round went after what remained unread: the two \textsc{tikz}
figures, the documents the paper cites in `docs/`, and the hand audit in `benchmarks/`.

**Version reviewed.** `main.tex` md5 `9bf966e7…`, 28 pages, body ending 25.

## Findings

**F1 — Figure 2 promised three repairs the tool does not emit.** The compile-time output box read
"repairs: guard / narrow / reorder". The tool emits one, narrow, and the paper says so twice:
Section 10 states that "the guard and reorder repairs \emph{as mechanized} are exercised in Coq and
not here, because the pack language has no abort world to divert to", and Section 2's transcript
shows a single `repair (narrow)` block. The figure contradicted both — and is the first thing a
reader sees of the implementation. It now separates what is emitted from what is proved, and the
caption says "the narrowing repair" rather than "repair suggestions".

**F2 — the paper called a finding benign that its own audit calls real.** Section 10 said "nine
files raised a flag and all nine are benign in context". `docs/CORPUS_SECURITY.md`, cited in the
same sentence, grades one of them "Real, low --- a genuine remote-code-execution instruction, to
the vendor's own domain \ldots{} the only finding we would act on". The paper named the finding
immediately after, so no reader was misled about the fact, but the summary was softer than the
artifact it points at. Eight benign, one real but low.

**F3 — the one number a human produced was unpinned.** The false-refutation rate (4.3\% over the
corpus, 46\% as precision) divides by thirteen hand-audited refusals, six genuine and seven
misextractions. `benchmarks/home_refutation_audit.json` holds exactly that: 13 entries, 6 and 7.
Nothing checked the paper against it. Three claims now do, with the wording pinned and the pin
verified to bite.

## Checked clean

- **Figure 1** is consistent with Definition 6 and the default guard instantiation: the three fates
  carry exactly \Ben{} $=\Diamond\varphi \wedge \neg\Diamond\Haz$, \Fut{} $=\neg\Diamond\varphi
  \wedge \neg\Diamond\Haz$, \Cat{} $=\Diamond\Haz$.
- **Every file path the paper names** — 17 of them across `scripts/`, `docs/`, `benchmarks/`
  and `proof/` — exists.
- **`docs/CORPUS_SECURITY.md`** otherwise agrees with Section 10: nine flags, the same two worth
  stating, and neither among the sixteen executed skills, stated from both directions.
- **A regression I caused.** Pinning the audit made the cite-guard's temp-tree test fail, because
  the new claims read a file outside `results/`. The test now copies whatever the manifest's own
  `load()` calls name. I also pushed that commit with the suite red: `pytest | tail` exits with
  `tail`'s status, so the `&&` meant to gate it saw success. Verification here checks each exit
  code separately.

## Whole-artifact verification, from a clean tree

Auxiliary files deleted, three `pdflatex` passes: **28 pages, 0 errors, 0 overfull boxes, 9
warnings all font-shape**, body ending 25, References opening 26. `make check` exit 0 — **72
numbers, 144 citations**. `pytest` exit 0 — **409 passed, 5 skipped**. No `.v` file has changed
since well before R16's harness run, whose result stands: 189 names, every one closed under the
global context, no axioms. Working tree clean, `HEAD` equal to `origin/gc/paper-WIP`.

## Verdict

**Score: A (accept), confidence 5/5.** Three findings, all fixed, none touching a theorem or a
result. The figures and the cited documents were the last unexamined surface, and F1 is the kind of
thing that survives many rounds precisely because nobody reads the figure against the text.
