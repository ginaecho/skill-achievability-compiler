# WIP: Typing the Unreliable Participant

Working draft of the **deviation-layer paper**: the base skill-achievability
discipline extended so that *the participant's compliance itself* is typed.
**Already in ECOOP shape**: LIPIcs class (`lipics-v2021`, `anonymous` option
for double-blind), ECOOP front matter (CCS concepts, keywords, running
title), and the conventional ECOOP structure (intro with contribution
bullets, §2 overview with a running example, formal sections, metatheory,
related work, conclusion). **Not for submission** — grep for
`DO-NOT-SUBMIT-WHILE-THIS-LINE-EXISTS`.

## Files

- `main.tex` — the full draft: §2 running example (booking session with an
  injectable fetcher), instrumented semantics, mode-graded typing rules,
  well-formedness conditions, seven theorems with proof obligations, the
  stochastic-game semantic model, pre-registered predictions.
- `lipics-v2021.cls`, `lipics-logo-bw.pdf`, `orcid.pdf`, `cc-by.pdf` —
  Dagstuhl's LIPIcs author class and assets (from
  `dagstuhl-publishing/styles`, master), vendored so the paper builds
  anywhere.

## Before actual submission (mechanical checklist)

- Drop the `anonymous` class option only for the camera-ready; fill real
  authors, ORCIDs, funding, acknowledgements, `\EventEditors` etc.
- Convert the inline `thebibliography` to `plainurl` + a `.bib` file
  (LIPIcs requirement) and resolve every entry marked `[to verify]`.
- Remove the `\thanks` draft banner, the `WIP:` boxes, and the
  `DO-NOT-SUBMIT` marker; re-enable `\linenumbers` if the CFP asks.
- Check the ECOOP CFP page limit (recent years: ~25 pp excluding
  references) and the double-blind instructions of that year.

## Authority and division of labor

- `../tas.tex` remains **authoritative for the base rules** (T-Comm, T-Act,
  T-Goal, T-End; S-Comm, S-Act; G-\*-E/I). Section 2 of `main.tex` restates
  them and must never diverge; on conflict, `tas.tex` wins.
- This draft owns the *extension only*: extended packs (`Crit`, `prov`,
  `Att`, `Rfr`), extended configurations `⟨𝕄; W; M; d; T⟩`, the instrumented
  LTS (I-Comm/I-Act/I-Refresh/I-Att/I-Dev/I-Quar, G-Dev, G-Goal-San), the
  mode-graded typing rules (T-Comm-M, T-Act-M, T-Refresh, T-Att, T-Goal-San,
  T-Quar), WF-Loop / WF-Att, and the compliance-profile game semantics.

## Design invariants (do not break while editing)

1. **No numbers in the rules.** Probabilities live only in the compliance
   profile `E = ⟨ε, κ, D⟩`, interpreted in the semantic model (§5). The rules
   carry only *shape*: monotone downgrade, taint propagation, grade reset,
   demonic bottom.
2. **Safety unconditional, achievement graded.** T2 (quarantine
   non-interference) must never depend on `E`.
3. **Conservativity** (Prop. 1): all-`ok` modes + empty taint + no `ext`
   provenance + `ε ≡ 0` collapses everything to the base discipline.
4. **Asymmetric trust dynamics:** modes go down by evidence, up only by
   attestation (T-Att); `✓φ` cleans *data* (taint), never *roles* (modes).

## Open design points (flagged `WIP:` in the text)

1. **T-Quar / quarantine residual `G ↾ p`** (Remark 1): syntactic escalation
   branches vs. partial residual whose undefinedness refutes with a new
   reason code (`UNQUARANTINABLE_ROLE`). Draft leans (b). Co-author to rule.
2. **Closure-premise strictness at ε ≡ 0** (Remark 2): should downgrade
   closure be demanded even when the profile predicts no deviation?
3. Bibliography entries marked `[to verify]` are placeholders; the base
   paper's `synthetic2023`/`synthetic2026` key mis-resolution must be fixed
   before reusing any related-work text.

## Mechanization plan (matches §6)

- **Coq** (extends `proof/`, axiom-free, same `Print Assumptions` harness):
  T1 instrumented subject reduction, T2 non-interference, T3(i–ii) mode
  monotonicity, Prop. 1(i–ii). Prerequisite: the multi-branch/`prt`
  mechanization of the base T-Comm (known gap in `DirectTypingSR.v`).
- **Paper proofs**: T3(iii), T4 graded soundness, T5 bounded degradation +
  negative converse (renewal argument — the substantive step), T6 complexity
  (imports Condon's SSG results), T7 undecidability (inherits base).

## Build

```
pdflatex main.tex && pdflatex main.tex
```

Requires the `libertine`, `newtx`, and `inconsolata` font packages
(TeX Live: `texlive-fonts-extra`) in addition to the base toolchain used by
`tas.tex`. The LIPIcs class and its assets are vendored in this directory.
