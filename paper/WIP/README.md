# WIP: Affordable Mistakes

Working draft: **severity-aware multiparty session types for agents that choose
wrongly.** The type system does not prevent an agent from taking branch `B`
when the task demanded `A`; it prevents wrong choices from being *catastrophic*
and reports the rest as risk. **Not for submission** — grep for
`DO-NOT-SUBMIT-WHILE-THIS-LINE-EXISTS`.

Already in ECOOP shape: LIPIcs class (`lipics-v2021`, `anonymous`), ECOOP front
matter, and the conventional structure (contribution bullets, §2 overview with
a worked example, formal sections, mechanized metatheory, related work).

## Files

- `main.tex` / `main.pdf` — the paper (9 LIPIcs pages).
- `proof/Severity.v` — **mechanizes §5–§7**, axiom-free, finite fragment.
- `proof/DeviationLayer.v`, `proof/AUDIT.md` — the mechanized audit that
  **refuted the predecessor draft** (modes/taint/grades) and motivated this
  reframing. Retained deliberately; summarized in §9 of the paper.
- `notes/blast-radius-reframing.md` — the design note behind the reframing.
- `NOVELTY.md` — ~30-search prior-art review with per-mechanism verdicts.
- `lipics-v2021.cls` + assets — vendored so the paper builds anywhere.

## The core idea in four lines

- **Guarded choice**: each branch carries the predicate making it *intended*;
  taking a branch whose guard fails is a **misselection**.
- **Severity**: a misselection is `Benign` (goal still reachable), `Futile`
  (goal lost, nothing harmed), or `Catastrophic` (hazard reachable).
  *Failure is not disaster.*
- **k-resilience**: no run with ≤ k misselections reaches a hazard.
  Possibilistic — **no probabilities anywhere**.
- **T-Choice-Safe**: intended branches checked at the same budget,
  misselectable ones at one less. Every affordable mistake is allowed; every
  unaffordable one is structurally unreachable.

## Verified results (`make` in `proof/`)

29 results across both developments, every one axiom-free.

| Result | Coq |
|---|---|
| Soundness of T-Choice-Safe | `TC_sound` |
| **Completeness** (exact characterization) | `TC_complete`, `TC_exact` |
| Severity is a partition | `severity_disjoint`, `severity_exhaustive` |
| Catastrophe ⟺ untypability | `catastrophe_implies_untypable`, `untypable_implies_catastrophe` |
| k-resilience downward closed | `resilience_downward_closed` |
| Resilience **anti**-monotone in Γ (least privilege) | `resilience_antitone_in_ctx` |
| Narrowing repair sound | `repair_narrow_sound` |
| Worked instance: 0-resilient, not 1-resilient, repaired | `Gbad_is_0_resilient`, `Gbad_not_1_resilient`, `Ggood_is_k_resilient` |

## Before submission

- Drop `anonymous`; fill authors, ORCIDs, funding, acknowledgements.
- Convert the inline bibliography to `plainurl` + `.bib` (LIPIcs requirement)
  and resolve entries marked `[to verify]`; add the citations `NOVELTY.md`
  flags as missing (Derakhshan/Balzer/Yao ECOOP 2024 above all).
- Remove the draft banner, `WIP:` boxes, and the `DO-NOT-SUBMIT` marker.
- Mechanize recursion and the remaining three repairs, or scope them explicitly.
- Run the three experiments in §8; no numbers are claimed until then.

## Build

```
pdflatex main.tex && pdflatex main.tex   # needs texlive-fonts-extra
cd proof && make                          # Coq 8.18
```
