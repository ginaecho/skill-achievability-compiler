# Prior-art audit of the deviation-layer paper

~30 targeted searches across the session-types, information-flow-control,
probabilistic-verification, and 2024–2026 agent-security literatures. Verdicts
are deliberately harsh: the point is to find what a reviewer would find.

## Per-mechanism verdict

| # | Mechanism | Verdict |
|---|---|---|
| 1 | Compliance modes (3-point lattice, monotone downgrade, attestation-only raise) | **PARTIALLY SCOOPED** at idea level |
| 2 | Taint fused into session typing; `✓φ` as sanitizer | **SCOOPED** |
| 3 | Typed irreversibility guard, demonic over compromised roles | **SCOOPED** conceptually |
| 4 | Grades = steps since re-grounding + cycle-checkpoint condition | **PARTIALLY SCOOPED** (one 2026 near-miss) |
| 5 | Mode-modulated 2½-player game + graded `◇≥p` | **PARTIALLY SCOOPED**; the *combination* looks open |

## The most dangerous citations (all currently missing from `sec:related`)

**Mechanism 2 is the weakest and must stop being presented as a contribution.**
- Derakhshan, Balzer, Yao. *Regrading Policies for Flexible Information Flow
  Control in Session-Typed Concurrency.* **ECOOP 2024**. IFC through session
  types with integrity labels, downgrading, and governed regrading policies —
  i.e. a session-typed sanitizer. Same venue. Single most dangerous citation.
- Derakhshan, Balzer, Jia. *Session Logical Relations for Noninterference.*
  LICS 2021 — the proof technique reviewers will expect us to relate to.
- Capecchi, Castellani, Dezani-Ciancaglini, Rezk. CONCUR 2010 / I&C 2014 —
  MPST with participant security levels **and controlled declassification**.
- Castellani, Dezani-Ciancaglini, Pérez. FAoC 2016 — monitors whose security
  levels are instantiated at runtime, with violation-triggered adaptation.

**Mechanism 3: robust declassification is our demonic quantification, 25 years old.**
- Zdancewic & Myers, *Robust Declassification* (CSFW 2001); Myers, Sabelfeld,
  Zdancewic, JCS 2006 — a property quantified over all attacker code at
  low-integrity holes, enforced by a type system.
- Cecchetti, Myers, Stefan. *Nonmalleable Information Flow Control.* CCS 2017.
- Corin et al. CSF 2007; Bhargavan et al. CSF 2009 — multiparty session
  integrity against an adversary controlling **an arbitrary subset of session
  participants**. Our ⊥-role quantification, for MPST, from 2007–09.
- Bartoletti et al. *Honesty by Typing.* FORTE 2013 / LMCS 2016 — a type system
  proving a process honours its contracts **in the presence of dishonest
  adversaries**. Threatens our headline framing more than any other paper.
- Riely & Hennessy. *Trust and Partial Typing in Open Systems of Mobile
  Agents.* POPL 1999 — good (typed) vs bad (arbitrary) sites. A reviewer will
  ask what our *middle* mode buys over a two-point split.

**Mechanism 4: a 2026 near-miss on our own theorem.**
- Fan, Tan, Wattenhofer, Ong. *Information Fidelity in Tool-Using LLM Agents:
  A Martingale Analysis of MCP.* AAMAS 2026 — cumulative distortion grows with
  steps; periodic re-grounding roughly every 9 steps suffices. Close to the
  contrapositive of our uncheckpointed-loop theorem, published earlier.
- Bocchi, Yang, Yoshida. *Timed Multiparty Session Types.* CONCUR 2014 — clocks
  reset per recursion instance under an *infinite satisfiability*
  well-formedness condition. Structurally our cycle-checkpoint condition, in
  MPST, in 2014.
- Das/Hoffmann/Pfenning resource-aware session types — "cycles must restore a
  budget" is the same schema. Graded modal types (Petricek/Orchard/Mycroft;
  Orchard et al. ICFP 2019; Marshall & Orchard on graded modal *session* types)
  are standard; no published grade means *staleness*, but that is an instance of
  the ℕ-semiring, i.e. an application.

**Mechanism 5.**
- Inverso, Melgratti, Padovani, Trubiani, Tuosto. *Probabilistic Analysis of
  Binary Sessions.* CONCUR 2020 — probability that a session **terminates
  successfully** from session types. Our `◇≥p` for the binary case.
- Aman & Ciobanu, imprecise/interval-probability MPST — MDP-shaped MPST with
  both probabilistic and nondeterministic choice.
- Bartolo Burlò et al. *Towards Probabilistic Session-Type Monitoring.*
  COORDINATION 2021 / PSTMonitor — monitors that warn when observed behaviour
  **deviates** from the specified distribution.
- Pro2Guard (arXiv:2508.00500) — probabilistic reachability model checking of
  unsafe LLM-agent states with PAC guarantees; our `◇≥p` as a runtime enforcer.
- Castellan & Yoshida, POPL 2019 — session types / game semantics correspondence.

**Agent-side prior art on taint-gating irreversible tool calls (all 2025–26):**
CaMeL (DeepMind), FIDES (Microsoft) — confidentiality *and integrity* labels
with deterministic pre-tool policy checks, Progent (*monotonic confinement* —
literally our monotone-downgrade-with-explicit-raise), LLMbda calculus
(termination-insensitive noninterference for agent conversations), and **ETAS:
An Effect-Typed Language for Agent Systems** (arXiv:2607.17780), whose
motivating question is literally about repeating irreversible operations.

**Framing competitors in the MPST-for-agents space:** *Provable Coordination for
LLM Agents via Message Sequence Charts* (arXiv:2604.17612); *NEST: Network
Enforced Session Types* (**ECOOP 2026**) — session-type monitors in the data
plane, which usefully corroborates our trusted-gate premise.

## What is actually defensible

> A *single* multiparty session typing judgment simultaneously indexed by (i) a
> per-role conformance mode derived from **observed protocol deviation** and
> (ii) a per-role staleness grade, in which **behavioural non-conformance of a
> role becomes a data-integrity label on the messages it sends**, so that a
> structural irreversibility side-condition is discharged statically and
> profile-independently, while the achievement half is quantitative over a
> mode-modulated 2½-player game.

The mode→taint contamination rule and the cycle-checkpoint condition *as a
typing precondition* (not a runtime heuristic) are individually defensible.
Nothing else in the current draft is.

## Two required changes

1. **Terminology collision.** "Compliance" is taken in session types, meaning
   client/server contract compliance (Barbanera, Dezani-Ciancaglini et al.,
   *Open Compliance in Multiparty Sessions*, COORDINATION 2022; JLAMP 2025).
   Rename to **conformance mode** or **fidelity mode**.
2. **Soundness cross-check.** The prior-art review independently predicted the
   exact defect the Coq audit then found: unrestricted endorsement is unsound
   (Cecchetti et al., CCS 2017), and a `✓φ` node that sanitizes whatever reaches
   it — when a ⊥-role can choose *which* value reaches the assertion — is the
   laundering pattern robustness was invented to rule out. See
   `proof/AUDIT.md`, Finding 2, for the mechanized counterexample. `✓φ` must be
   made a **robust** endorser.
