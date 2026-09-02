# Mechanized audit of the WIP deviation-layer paper

`DeviationLayer.v` (650 lines, Coq 8.18, stdlib only, **axiom-free**) encodes the
definitions of `paper/WIP/main.tex` as literally as possible and then *tries* to
prove the theorem statements. It assumes none of them. Where a statement is
provable it is proved; where it is not, a concrete counterexample is constructed
and proved.

```
coqc DeviationLayer.v && coqc check_dev.v && coqc check_co.v
```

All 14 results print `Closed under the global context`.

## Verdict table

| Paper claim | Status | Coq name |
|---|---|---|
| Mode lattice: `down`/`meet` monotone | **PROVED** | `down_monotone`, `meet_monotone` |
| Contamination update monotone (needed by thm:modes ii) | **PROVED** | `contamination_monotone` |
| thm:noninterf — *syntactic* reading | **PROVED (but trivial)** | `irr_safe_invariant` |
| thm:noninterf — *semantic* reading | **REFUTED** | `taint_laundering_refutes_noninterference` |
| proposed repair to the taint update | **PROVED** | `repaired_update_blocks_laundering` |
| thm:isr — head-role deviation | **PROVED** | `sr_dev_head_preserved` |
| thm:isr — under a total quarantine residual | **PROVED** | `sr_dev_with_total_qres` |
| **the type system is non-vacuous** | **REFUTED** | `act_vacuous_with_partial_qres`, `goal_then_act_vacuous` |
| … and not an artifact of inductive reading | **REFUTED coinductively too** | `act_vacuous_coinductive` |
| thm:checkpoint — positive direction from WF-Loop | **REFUTED** | `goal_only_cycle_hits_cap` |
| proposed repair to WF-Loop | **PROVED** | `wfloop_refresh_grade_bounded` |

## Finding 1 (blocking) — the type system is vacuous as drafted

`T-Act-M` and `T-Comm-M` each carry a *downgrade-closure* premise that recurses
**at the same protocol node** with the acting role's mode lowered. The mode
lattice has three points, so the chain is `ok → dr → ⊥` and then stops: at `⊥`,
`T-Act-M`'s own premise `M(p) ≠ ⊥` fails, so only `T-Quar` can apply. `T-Quar`
needs the quarantine residual `G ↾ p` of Remark 3 to be **defined**.

Remark 3 prefers option (b): a *partial* residual whose undefinedness refutes.
Those two choices are inconsistent. With a partial residual, **no protocol whose
head is a capability is typable at all** — hence `Ach-M` is underivable for any
pack that uses a tool, and `thm:isr` holds only vacuously.

`act_vacuous_coinductive` shows this is not an artifact of reading `⊢`
inductively: the chain descends strictly in a finite lattice and ends in an
unsatisfiable obligation, so the greatest fixed point excludes those
configurations too.

**Fix (pick one):**
1. make `qres` total (Remark 3 option (a): every choice node involving a role
   carries an explicit escalation branch), or
2. drop the closure premises from `T-Act-M`/`T-Comm-M` and instead *prove*
   downgrade closure (thm:modes ii) as a lemma — but then thm:modes (ii) must
   itself handle the `⊥` case, which again needs a total residual, or
3. bound the closure premise to modes `≠ ⊥`, i.e. require typability only after
   downgrades that stay above bottom, and treat reaching `⊥` as a separate
   *safety* obligation rather than a typing one.

Option 3 is the smallest change and keeps the refutation asymmetry the
discipline is built on. Whichever is chosen, the paper cannot leave Remark 3
open *and* state thm:isr unconditionally.

## Finding 2 (soundness) — the taint update launders external data

The paper's update is

```
T ⊕_a M  =  T ∪ wr(a)   if  M(p) ⊑ dr  ∨  prov(a) = ext
            T           otherwise
```

It consults the **writer's mode** and the **capability's provenance** — never
what the capability **reads**. So an `ok`-mode, internal-provenance capability
that copies a tainted variable into a fresh one produces a *clean* variable
holding attacker-controlled data.

The mechanized counterexample: `fetch` (external) writes `fare`, so `fare` is
tainted; `copy` (internal, `ok` role) sets `fareok := fare` and the taint set is
**unchanged**; the irreversible `purchase`, guarded by `fareok ≤ 500`, then
passes `supp(pre) ∩ T = ∅`. Two runs differing *only* in the fetched value
differ in whether the irreversible action fires — precisely the interference the
theorem's name promises to exclude.

This also shows that `irr_safe_invariant` (the theorem as literally stated) is
proved in one line by re-reading `I-Act`'s own premise. It is a restatement of a
side condition, not a property of the taint *analysis*. The paper should either
rename it (e.g. *irreversibility guard invariant*) or strengthen it to a genuine
two-run non-interference statement — the latter is the interesting theorem and
is what a PL reviewer will expect from the name.

**Fix:** add a read set to capabilities and propagate,
`reads(a) ∩ T ≠ ∅ ⟹ T ∪ wr(a)` (`taint_upd_fixed`, verified to block the
counterexample). Then state and prove the two-run property.

## Finding 3 (statement bug) — WF-Loop does not bound grades

Definition 3 accepts a cycle containing *either* a goal marker `✓φ` *or* a
refresh. But `✓φ` sanitizes **taint**; only `T-Refresh` resets a **grade**. A
cycle whose only checkpoint is a goal marker therefore lets grades tick to the
cap and stay there (`goal_only_cycle_hits_cap`), so the regeneration premise of
the renewal argument behind thm:checkpoint's positive direction does not hold
for all WF-Loop protocols.

**Fix:** require a refresh (not merely a goal marker) in every cycle for the
grade-bounding half — `wfloop_refresh_grade_bounded` verifies that this does
give regeneration. Keep the goal-marker alternative only for the *taint*
obligation, which is a genuinely separate well-formedness condition. In other
words, WF-Loop should be split into WF-Loop-Taint and WF-Loop-Grade.

## What is *not* audited here

`thm:graded`, `thm:complexity`, `thm:undec`, and thm:modes(iii) are
game-theoretic/probabilistic and out of scope for this development; they are
paper-proof targets. Note that thm:graded depends on thm:isr and thm:noninterf,
so it inherits Findings 1 and 2 until those are repaired.


---

# Developments added after the audit (the reframed design)

All axiom-free; `make` in this directory runs every `Print Assumptions` harness.

## `Severity.v` — the severity discipline, finite fragment (18 results)

| Result | Coq |
|---|---|
| T-Choice-Safe sound / complete / exact | `TC_sound`, `TC_complete`, `TC_exact` |
| Severity is a partition | `severity_disjoint`, `severity_exhaustive` |
| Catastrophe ⟺ untypability | `catastrophe_implies_untypable`, `untypable_implies_catastrophe` |
| Budget downward-closed | `tolerance_downward_closed` |
| Reachability monotone in Γ ⇒ tolerance anti-monotone | `reach_monotone_in_ctx`, `tolerance_antitone_in_ctx` |
| Narrowing repair sound | `repair_narrow_sound` |
| Modular sequential composition, interface form | `TC_seq`, `TC_seq_interface`, `ends_budget_le` |
| Worked instance | `Gbad_is_0_tolerant`, `Gbad_not_1_tolerant`, `Ggood_is_k_tolerant`, `Ggood_by_narrowing` |

## `Bridge.v` — from protocols to PROGRAMS (4 results)

| Result | Coq |
|---|---|
| One instrumented head step preserves typing and debits the budget exactly | `bridge_step` |
| A typed session of a k-tolerant protocol is hazard-free on every run of cost ≤ k | `bridge_run` |
| Budgets distribute over participants (per-role allowances summing to ≤ k) | `budget_distributes`, `total_eq_sum_percost` |

Scope: head-move semantics of the finite fragment, matching the base
`DirectTyping.v`. `Mu.v` lifts the bridge to recursive sessions.

## `Regular.v` — regular protocols (8 results)

| Result | Coq |
|---|---|
| Budgeted reachability ⟺ reachability in the product Node × World × {0..k} | `product_correspondence` |
| Budget is a monotone counter; a path with d misselection edges has d ≤ b (loop re-entry bounded) | `budget_never_increases`, `dev_edges_bounded`, `dev_edges_exact` |
| Reachability witnessed by a path no longer than the reachable-state count (pigeonhole) | `reach_bounded_path` |
| Executable decision procedure, sound and complete (node list need only be successor-closed) | `decide_sound`, `decide_complete`, `decide_reachb_correct` |

## `Mu.v` — μ-types: the two developments connected (10 results)

| Result | Coq |
|---|---|
| Unfolding is substitution; the substitution lemma behind finiteness | `subst_comp`, `unfold_close` |
| The unfolding closure `cands` is finite and closed under every step; every reachable state is in it | `cands_closed`, `reach_in_cands` |
| One typed session step simulates a protocol path of the same cost; the bridge for recursive sessions | `sim_step`, `bridge_mu` |
| The finite fragment embeds; T-Choice-Safe = non-reachability in the product; the finite bridge recovered | `reach_embed`, `TC_regular`, `bridge_finite_via_mu` |
| Decision procedure for μ-types, sound and complete | `decide_mu_correct` |

## `Repairs.v` — the four repairs (13 results)

| Result | Coq |
|---|---|
| Guard: sound, exact; a misselected guarded branch is stuck | `repair_guard_sound`, `repair_guard_exact`, `guard_absorbs_misselection` |
| Reorder: sound under commutation + harmlessness; validations commute; exact forms; the PNR theorem | `repair_reorder_sound`, `validation_commutes`, `reorder_original_exact`, `reorder_reordered_exact`, `repair_reorder_pnr` |
| Compensate: sound (TC_seq); Futile → Benign | `repair_compensate_sound`, `repair_compensate_restores_goal` |
| Worked instance: purchase-before-verify is not 1-tolerant; verify/purchase commute; reordered is k-tolerant | `Gbad2_not_1_tolerant`, `commutes_verify_purchase`, `Greordered_is_k_tolerant` |

## `Interleave.v` — bystander interleavings (10 results)

| Result | Coq |
|---|---|
| Safe swaps (action/action, action/choice, action/goal in both directions, and two communications between disjoint role pairs) preserve the condition / typing; interleaved runs are hazard-free within budget | `swap_safe`, `swap_ctypes`, `swaps_safe`, `swaps_ctypes`, `bridge_interleaved` |
| STRIPS variable disjointness discharges commutation, enabledness, guard preservation, hazard neutrality, and hence every side condition of an action swap | `strips_commute`, `strips_enables`, `strips_preserves`, `strips_neutral`, `strips_swap_act` |

## `Kernel.v` — the verified kernel (3 results) and `Regular.v` additions

| Result | Coq |
|---|---|
| Deduplicating, early-exiting reachability, sound and complete (Regular.v) | `decide'_sound`, `decide'_complete` (counted in Regular.v's 8 via the harness of `decide_reachb_fast_correct`) |
| The kernel's budgeted decision is correct on bit-vector worlds with STRIPS actions | `kernel_correct`, `kernel_first_spec` |
| Goal reachability used by the elaboration is correct | `goal_reachable_correct` |

Trusted, not proved: the elaboration `elab` (Coq, executable) and the exporter
`src/skillc/kernel.py` that turn a pack into the kernel's input.
