# WIP: Affordable Mistakes

Working draft: **severity-aware multiparty session types for participants that
choose wrongly.** The discipline does not prevent an agent from taking branch
`B` when the task demanded `A`; it prevents wrong choices from being
*catastrophic*, reports the rest as risk, and carries the guarantee from the
protocol to the typed session. **Not for submission** — grep for
`DO-NOT-SUBMIT-WHILE-THIS-LINE-EXISTS`.

In ECOOP shape: LIPIcs class (`lipics-v2021`, `anonymous`), ECOOP front matter,
four TikZ figures, and the conventional structure.

## What is in this directory

| path | content |
|---|---|
| `main.tex` / `main.pdf` | the paper |
| `fig/` | figures (TikZ sources + PNG exports) |
| `proof/Severity.v` | the condition, exactness, partition, monotonicity, narrowing, **modular composition** (18) |
| `proof/Bridge.v` | **(A)** from protocols to programs: `bridge_step`, `bridge_run`, `budget_distributes` (4) |
| `proof/Regular.v` | **(B)** regular protocols: product, loop/budget lemma, pigeonhole, executable decision procedure (8) |
| `proof/DeviationLayer.v` + `proof/AUDIT.md` | the mechanized audit that refuted the predecessor draft (14) |
| `results/severity.json` | **(C)** raw evaluation output |
| `../../docs/SEVERITY_RESULTS.md` | evaluation tables |
| `../../src/skillc/severity.py` | the implementation (`skillc severity <pack.json|SKILL.md>`) |
| `../../src/skillc/data/severity_corpus.json` | the 15-protocol severity benchmark with pre-stated expected verdicts |
| `../../scripts/severity_eval.py` | the evaluation, including the modularity experiment |
| `../../tests/test_severity.py` | tool verdicts checked against the Coq instances |
| `NOVELTY.md`, `NOVELTY-v2.md` | prior-art audits (withdrawn draft; current design) |
| `notes/` | design notes |

## The core idea

- **Guarded choice**: each branch carries the predicate making it *intended*;
  taking a branch whose guard fails is a **misselection**. Default guard when
  none is written: the goal survives the branch (rational choice).
- **Severity**: `Benign` (goal still reachable), `Futile` (goal lost, nothing
  harmed), `Catastrophic` (hazard reachable). *Failure is not disaster.*
  Default hazard: an irreversible tool fires after the goal is lost.
- **k-misselection tolerance**: no run with ≤ k misselections reaches a hazard.
  Possibilistic — no probabilities. The tolerance degree `k*` is the headline.
- **T-Choice-Safe**: exact syntax-directed characterization.
- **Bridge**: a session typed against a k-tolerant protocol is hazard-free
  within budget k; budgets distribute over participants.

## Verified results — `make` in `proof/`

**44 results, every one axiom-free** (`Print Assumptions` harnesses).

## Evaluation headline (`python3 scripts/severity_eval.py`)

- Existing corpora (15 + 6 achievability packs, 17 real skills): **no
  irreversible effects, and the real skills have no choice points** — the
  question is invisible to them.
- Severity benchmark (15 protocols, 40 branches, 0.22 s): 26 Benign / 3 Futile /
  11 Catastrophic; `k*` = 0 for 7, 1 for 2, ≥5 for 6; PNR actions purchase,
  send, deploy, delete, ship, purge, refund, drop_old, commit. 14/15 matched
  pre-stated expectations; the 15th was a benchmark authoring error, fixed.
- Modularity: whole-system complete analysis 35.8 s at n=6 vs 0.13 s modular
  with the cone-of-influence interface (concrete interface: 2.9 s, 256 points).
  Re-check after a change: 172 ms vs 22 ms.

## Before submission

- Drop `anonymous`; fill authors, ORCIDs, funding, acknowledgements.
- Inline bibliography → `plainurl` + `.bib`; resolve `[to verify]` entries.
- Remove the draft banner, `WIP:` boxes, and the `DO-NOT-SUBMIT` marker.
- Connect `Bridge.v` (finite fragment) and `Regular.v` (finite graphs) through
  μ-unfolding; mechanize the guard and reorder repairs.
- Run the predictive-validity experiment with live agents.

## Build

```
pdflatex main.tex && pdflatex main.tex     # needs texlive-fonts-extra
cd proof && make                            # Coq 8.18
pip install -e ../.. && python3 ../../scripts/severity_eval.py
```
