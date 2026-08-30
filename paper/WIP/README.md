# WIP: Typing the Unreliable Participant

Working draft of the **deviation-layer paper**: the base skill-achievability
discipline extended so that *the participant's compliance itself* is typed.
Target shape: ECOOP research paper (to be reformatted to LIPIcs when the
rules stabilize). **Not for submission** — grep for
`DO-NOT-SUBMIT-WHILE-THIS-LINE-EXISTS`.

## Files

- `main.tex` — the full draft: instrumented semantics, mode-graded typing
  rules, well-formedness conditions, theorem statements T1–T7 with proof
  obligations, the stochastic-game semantic model, pre-registered predictions.

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

Plain `article` class for now (same toolchain as `tas.tex`); port to
`lipics-v2021` once rules stabilize.
