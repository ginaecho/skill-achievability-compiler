# Reframing: from "typing compliance" to "typing the blast radius of a wrong choice"

Origin: co-author observation. Agents are nondeterministic *at choice points* —
the agent should select `A` and selects `B`. The type system must not try to
prevent that. It must prevent **catastrophe**, and to do that it must be
**context aware**: does choosing `B` *here*, in *this* world state, cascade to
something unrecoverable?

This note replaces the mode/taint/grade framing as the paper's core. Modes and
taint survive only as a refinement (see §8).

## 1. The object of study

Classical MPST: `G` says which interactions are *possible*.
This paper: `G` + `Γ` + `φ_goal` says which *mistakes you can afford*.

Thesis line: **session types say what may happen; this says what you can
survive.**

## 2. Deviation at a choice node

At `p→q:{ℓᵢ.Gᵢ}_{i∈I}` with world `W`, let the intended branch be `ℓₖ`. A
*misselection* is the agent taking `ℓⱼ`, `j ≠ k` (in-set deviation — the
interesting case; out-of-set is already a blocked stutter at the gate).

Severity is a function of the *node and the world*, not the label alone:
choosing "skip-validation" is benign before payment and catastrophic after.
This is exactly why plain MPST cannot answer the question and a world-tracking
discipline can.

## 3. The severity lattice

For hazard predicate `H` (safety) and goal `φ`, classify the residual
configuration `(Gⱼ, W)`:

```
sev(ℓₖ ⇝ ℓⱼ, W) =
  Benign        if  ◇φ  ∧  ¬◇H            -- detour; goal still reachable
  Recoverable   if  ◇φ only via a compensation region  ∧  ¬◇H
  Futile        if  ¬◇φ  ∧  ¬◇H           -- failure, not disaster
  Catastrophic  if  ◇H                     -- hazard reachable
```

`Benign ⊑ Recoverable ⊑ Futile ⊑ Catastrophic`.

Note `Futile ≠ Catastrophic`. That distinction is the practical payload: most
wrong choices lose the goal without hurting anyone, and a system that blocks
them is useless.

## 4. Catastrophe is computable: the point of no return

**Definition (point of no return).** `(G,W)` is a PNR for `φ` if `¬◇φ`.
An action `a@p` at `(G,W)` is *goal-destroying* if `◇φ` holds at `(G,W)` and
fails at every successor.

**Key structural fact.** Effects are STRIPS. An atom in `Del_a` can only be
restored by some `b` with the atom in `Add_b`. If no such `b` is in `Γ`, the
loss is permanent. That is exactly the **establisher closure** the existing
checker already computes for protocol-independent refutation
(`_gamma_refutation` in `src/skillc/checker.py`).

So: **catastrophic = irreversible ∧ unrecoverable**, and both halves are
already decidable in the existing widened fragment. The paper does not need new
machinery to *detect* catastrophe — it needs to run the machinery it has,
pointwise at every deviation.

## 5. Cascading: the k-deviation budget

A single wrong choice may be benign while two compose into catastrophe. Model
it directly:

**Definition (k-resilience).** `G` is *k-resilient* for hazard `H` under `Γ` if
no run containing at most `k` misselections reaches `H`.

- `0-resilient` = classical MPST safety (no deviation).
- `1-resilient` = no single wrong choice is catastrophic.
- `k-resilient` = the honest engineering target.

Decidable by the same finite forward search, on the product of the existing
abstract state space with a counter `0..k` — a factor `(k+1)` blowup, nothing
more. This is where the complexity theorem the audit asked for now lives, and
it is *possibilistic*: **no probabilities needed for the safety story at all.**

## 6. The typing rule

The type system does not forbid `B`. It requires every catastrophic branch to
be *guarded*:

```
[T-Choice-Safe]
  ∀ i ∈ I.  sev(ℓᵢ, W) ⊑ Futile
            ∨  ℓᵢ is guarded (preceded by ✓φ / attestation)
            ∨  ℓᵢ is compensable (a recovery path re-establishes ◇φ)
  ─────────────────────────────────────────────────────────────
  p→q:{ℓᵢ.Gᵢ}_{i∈I} ⊢ ...
```

Well-typed therefore means: *every affordable mistake is allowed, every
unaffordable one is structurally impossible.*

## 7. What the checker reports — the risk verdict

The verdict stops being binary. Per choice node, the tool emits:

| field | content |
|---|---|
| node | protocol position + world abstraction |
| branch | the label that would be misselected |
| severity | Benign / Recoverable / Futile / Catastrophic |
| witness | the concrete path to the hazard (for Catastrophic) |
| PNR step | the exact action that crosses the point of no return |
| repair | which of the four patterns below applies |

The headline number for a pack becomes its **resilience degree**: the largest
`k` for which it is `k`-resilient. `k = 0` on a pack that calls a destructive
tool is the actionable finding.

## 8. The four repairs (the "safe way to state a safe interaction")

1. **Guard** — insert `✓φ` or an attestation before the irreversible branch.
   Catastrophic → guarded.
2. **Compensate** — add a recovery path from the deviated branch back to a
   goal-reachable configuration. Catastrophic/Futile → Recoverable.
3. **Narrow the offer** — remove the catastrophic label from the choice set, so
   the gate refuses it and the deviation becomes a blocked stutter rather than
   a state change.
4. **Reorder** — move the irreversible action after the validation, so no
   *single* deviation can reach it. This is the repair that raises `k`.

**Theorem target (repair soundness).** Each pattern is severity-monotone, and
applying pattern 4 exhaustively yields a `1`-resilient protocol whenever one
exists over the same `Γ`.

Modes/taint from the previous draft survive here, narrowly: they are what makes
the *injection* case computable (an externally-sourced payload is the world
input an attacker controls, so `◇H` must be evaluated demonically over it).
They are a refinement of `sev`, not the paper's core.

## 9. Theorem set

- **T-A** severity is decidable in the widened fragment; complexity bound.
- **T-B** `k`-resilience is decidable; product-with-counter construction;
  `O((k+1) · 2^|Pred| · |G|)` states.
- **T-C** **typing soundness**: `[T-Choice-Safe]`-well-typed with budget `k`
  ⟹ every run with ≤ `k` misselections satisfies `□¬H`. Profile-independent.
- **T-D** repair soundness + minimality.
- **T-E** ~~enlarging `Γ` cannot increase severity~~ **— REFUTED by the
  mechanization.** Reachability is monotone in `Γ`, so hazard reachability is
  too: adding tools opens new paths to the hazard as well as new recoveries.
  Corrected and proved: `k`-resilience is **anti-monotone** in `Γ`
  (`resilience_antitone_in_ctx`) — granting a capability can only lower the
  resilience degree. This is the formal argument for least privilege, and is a
  better result than the one predicted. `k`-resilience is downward closed in
  `k` (`resilience_downward_closed`).
- **T-F** characterization: a deviation is catastrophic iff it crosses a point
  of no return, computable by establisher closure.

## 10. What this fixes from the mechanized audit (`proof/AUDIT.md`)

- **Finding 1 (vacuity) — dissolved.** The downgrade-closure premise that
  recursed at the same node and made the system vacuous is gone. Deviation is
  quantified in the *semantics* (the `k`-budget), not by a recursive typing
  premise. No quarantine residual is needed, so Remark 3 disappears.
- **Finding 2 (taint laundering) — narrowed.** Taint is no longer load-bearing
  for the headline theorem; where it is used it must still carry the read-set
  repair and robust endorsement (Cecchetti et al., CCS 2017).
- **Finding 3 (WF-Loop) — subsumed.** Loop degradation becomes a `k`-budget
  question rather than a grade-reset question.
- **T-C is non-vacuous and provable**, unlike the drafted `thm:isr`.

## 11. Novelty position

Closest prior art to engage honestly:
- **Dead-end / unsolvability detection in classical planning** (Hoffmann et
  al.) — this is `¬◇φ` detection, well studied. Our lift is to a *protocol*
  with roles and choice points.
- **Reversibility and side-effect measures in RL safety** (attainable utility,
  reachability-preservation) — same intuition, no types.
- **Crash-stop MPST** (Barwell/Scalas/Yoshida ECOOP 2022) and
  **protocol-induced recovery** (Neykova/Yoshida CC 2017) — failures and
  recovery in MPST, but no severity classification and no goal reachability.
- **Shielding** (Alshiekh et al.) — runtime, single-agent, no protocol.
- `k`-fault-tolerance is classical in distributed computing; the novelty is
  `k`-*misselection* resilience tied to goal reachability in a session type.

Defensible claim: **a static, pre-execution severity analysis that classifies
each possible wrong choice of an agent participant by whether it is survivable,
and a typing discipline that admits every survivable mistake while making
unsurvivable ones structurally unreachable.**


---

## Status update (after mechanization)

`proof/Severity.v` mechanizes this design, axiom-free, for the finite fragment.
Proved: **T-C soundness AND completeness** (`TC_sound`, `TC_complete`,
`TC_exact` — the rule system is an *exact* characterization of k-bounded
hazard-freedom, so a typing failure is a genuine risk), the severity partition,
the catastrophe/untypability correspondence, budget downward-closure,
Γ-antitonicity (correcting T-E above), narrowing-repair soundness, and the
worked instance (0-resilient, not 1-resilient, repaired).

Not yet mechanized: recursion (the finite fragment only), and repairs 1, 2, 4
(guard, compensate, reorder).
