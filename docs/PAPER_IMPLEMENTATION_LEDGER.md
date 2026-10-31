# Paper-to-implementation ledger: "Affordable Mistakes" (v11, 23 pages, built 2026-09-02 21:04 UTC)

Every claim the paper makes that a reader could check against the repository, with its
status on this branch. Status values: **present** (artifact exists, runs, and matches the
paper's statement), **partial** (exists but differs or is incomplete), **missing**.
The ledger is re-checked after every implementation round; nothing is marked present
without running it.

The paper's own status box says: Sections 5–9 mechanized, 93 results, all `Print
Assumptions` closed; evaluation numbers real (`scripts/severity_eval.py`, results in
`paper/WIP/results/`). The post-v11 review rounds (R12–R20) raised the count to 189 Coq
names and added `cone_is_not_degenerate`, `congruence_is_not_degenerate`,
`Ggood_is_robust`, `strips_cap_cone`, `principal_characterises` (k* characterisation),
a numbers manifest tied to `results/` and a `cite` guard; those are listed at the end.

## A. Coq development (paper §4–§9, §11, §13)

Files the paper names: `proof/` (status box), `Mu.v`, `Interleave.v`, `Regular.v`,
`Kernel.v`, `Repairs.v`; plus `Severity.v` and `DeviationLayer.v` already on main.

| # | Paper statement | Coq name(s) | Status |
|---|---|---|---|
| A1 | §2 worked instance: G_bad 0-tolerant, not 1-tolerant; narrowed is k-tolerant | `Gbad_is_0_tolerant`, `Gbad_not_1_tolerant`, `Ggood_is_k_tolerant` | present (Severity.v) |
| A2 | Def 2 budgeted reachability | `reach_haz` | present (Severity.v) |
| A3 | Thm 6 trichotomy ordered | `reach_mono_budget`, `severity_monotone_in_budget`, `benign_step_up`, `benign_no_regress`, `benign_step_down`, `catastrophic_upward`, `futile_downward`, `tolerance_degree_is_a_threshold`, `severity_classes_are_separated`, `reach_mu_iff_run` | to check |
| A4 | Thm 7 partition | `severity_disjoint`, `severity_exhaustive` | present (Severity.v) |
| A5 | Thm 9 exact characterisation | `TC_sound`, `TC_complete`, `TC_exact`; `tolerance_downward_closed`, `tolerance_antitone_in_ctx` | present (Severity.v) |
| A6 | Def 10 instrumented head-move semantics | `hstep` | missing |
| A7 | Thm 11 bridge | `bridge_step`, `bridge_run` | missing |
| A8 | Thm 12 progress under misselection | `progress`, `every_label_steps` | missing |
| A9 | Thm 13 budgets distribute over participants | `budget_distributes` | missing |
| A10 | Thm 14 bridge, recursive (Mu.v: `ctypes`, `hstep`) | `sim_step`, `bridge_mu`, `bridge_finite_via_mu` | missing |
| A11 | Thm 15 bystanders (Interleave.v) | `swap_safe`, `swap_ctypes`, `bridge_interleaved` | missing |
| A12 | Thm 16 STRIPS variable disjointness | `strips_commute`, `strips_enables`, `strips_preserves`, `strips_neutral`, `strips_swap_act` | missing |
| A13 | Thm 17 product (Regular.v) | `product_correspondence` | missing |
| A14 | Thm 18 loops meet the budget | `budget_never_increases`, `dev_edges_bounded`, `dev_edges_exact` | missing |
| A15 | Thm 19 decidability | `decide_reachb`, `decide_sound`, `decide_complete`, `reach_bounded_path`, `decide_reachb_correct` | missing |
| A16 | Thm 20 unfolding closure finite (Mu.v: `Gr`, `reach_mu`) | `cands_closed`, `reach_in_cands`, `subst_comp`, `unfold_close` | missing |
| A17 | Thm 21 embedding | `reach_embed`, `TC_regular` | missing |
| A18 | Thm 22 decidability for mu-types | `decide_mu`, `decide_mu_correct` | missing |
| A19 | Prop 23 tolerance degree computable, PSPACE (paper proof only) | — | n/a (paper) |
| A20 | Thm 24 modular composition | `TC_seq`, `TC_seq_interface` | present (Severity.v) |
| A21 | §10 verified kernel (Kernel.v) | `kernel_first_spec`, `goal_reachable_correct`, `decide'_sound`, `decide'_complete`; extraction to OCaml | missing |
| A22 | Thm 25 narrow | `repair_narrow_sound` | present (Severity.v, check name) |
| A23 | Thm 26 guarded branch futile not stuck | `validates_ab_enabled`, `reach_halted`, `safeT_halted`, `guard_abort_is_futile` | missing |
| A24 | Thm 27 guard | `repair_guard_exact`, `guard_absorbs_misselection` | missing |
| A25 | Thm 28 reorder | `repair_reorder_sound`, `reorder_original_exact`, `reorder_reordered_exact`, `repair_reorder_pnr` | missing |
| A26 | Thm 29 compensate | `repair_compensate_sound`, `repair_compensate_restores_goal` | missing |
| A27 | §11 booking instance | `Gbad2_not_1_tolerant`, `commutes_verify_purchase`, `Greordered_is_k_tolerant` | missing |
| A28 | §13 refuted predecessor | `act_vacuous_with_partial_qres`, `act_vacuous_coinductive`, `taint_laundering_refutes_noninterference`, `goal_only_cycle_hits_cap` | present (DeviationLayer.v) |
| A29 | Assumption 5 as hypothesis, never an axiom; no classical principle; `Print Assumptions` harness for every result | `check_sev.v` etc. | partial (harness for Severity.v only) |

## B. Tool (paper §2, §10)

| # | Paper statement | Artifact | Status |
|---|---|---|---|
| B1 | `skillc severity`: per-branch severity, k*, first hazard witness, point-of-no-return action, narrowing repair, bystander pairs to serialize; k_max = 4 | `src/skillc/severity.py`, CLI subcommand | missing |
| B2 | Default rational-choice guards; default hazard = irreversible action while goal lost; explicit guard/hazard overrides; declared-irreversible tools; environment-controlled choices resolved demonically | same | missing |
| B3 | Output format of §2 (`migration_backup: tolerance degree k* = 1 ...` listing, incl. `keep_old Futile misselection` line, branch counts, bystander summary) | CLI; a test diffs CLI output against the paper block | missing |
| B4 | Fifteen tests check tool verdicts on the paper's instances against the Coq development's | `tests/test_severity.py` | missing |
| B5 | `skillc severity --verified`: extracted OCaml kernel on the boolean fragment; agrees on the 16 in-fragment benchmark protocols in < 50 ms each | `proof/Kernel.v` extraction + Python elaboration (~100 lines Coq + ~100 Python) | missing |
| B6 | Differential test: random packs in the shared fragment, 499 protocols over two seeds, 0 disagreements | `scripts/differential_test.py` | missing |
| B7 | Front-end rule: a fenced code block is an invocation of the shell | front end | to check |
| B8 | `skillc autocheck`: escalate to LLM compaction when the pack is weak; 130/162 escalated in home runtime, 49 in file-only | CLI subcommand | missing |
| B9 | Recording pass no longer stops at the first hazardous branch (bug found by Finding 4) | severity analyser | missing |

## C. Deterministic evaluation (no model tokens)

| # | Paper statement | Artifact | Status |
|---|---|---|---|
| C1 | Finding 1: 15-pack corpus, its 6-pack extension and 17 vendor skills compiled by the deterministic front end contain no irreversible effect and (the 17) no choice point; trivially tolerant | `scripts/severity_eval.py` census | missing |
| C2 | Finding 2 / Table 1: 17 authored protocols with provenance notes stating the expected verdict before running; 55 branch verdicts: 29 Benign, 7 Futile, 19 Catastrophic; k* 9x0, 2x1, 6x>=5; total 0.33 s; one authoring error found and recorded | `benchmarks/severity/*.json` (or similar) + results | missing |
| C3 | Bystander check on the two release protocols: audit release exact (five independent pairs), cache release two pairs to serialize | same | missing |
| C4 | Three pairs: repairs restore tolerance; severity property of node and world (insurance claim); PNR depends on Γ's establishers (rollback) | same | missing |
| C5 | Finding 3 / Table 2: migration segment chained n=1..6 at k=2: whole-system complete enumeration vs modular concrete exits vs modular projected (cone of influence); re-check cost after replacing last segment; deployment segment 728 ms vs 59 ms at n=6 | `scripts/severity_eval.py --chains` | missing |

## D. Evaluation that needs model calls (Claude sub-agents; CLAUDE.md rules: URL-scrubbed prompts, sandbox, no credentials)

| # | Paper statement | Artifact | Status |
|---|---|---|---|
| D1 | Finding 4: live agents, two production models (small, mid), plain vs pressured, 5 runs per protocol x model x condition = 340 runs, 400 decisions; every catastrophe exceeded k*; catastrophe rate ordered by k* (0/120 on k*>=5, 7/220 on k* in {0,1}); 6 of 19 Catastrophic branches taken by a live agent; earlier prompt form re-run and reported | `scripts/live_agents.py`, `results/` | missing |
| D2 | Finding 5: 162 real skills (17 vendor + 145 third-party, 12 repos, de-duplicated by hash, provenance recorded), two runtimes; 149 certified at home, 108 refuted file-only, 95 flip, 13 refuted at home; hand audit of the 13 (6 genuine, 7 misextractions = 4.3 % false refutation); census 1.8 s | `benchmarks/home_refutation_audit.json`, census script | missing |
| D3 | Finding 5 / Table 3: 134 verified runs (8 real skills x 2 runtimes x 2 models x 2 runs; 9 spec pairs A/B; 5 skills at realistic scale); artifact verification by recomputation; costs and tokens per row | `benchmarks/spec-cases/`, run harness, verifiers | missing |
| D4 | Grep baseline: 25 vs 34 on the 34 independently-known configurations, 0.2 ms | `scripts/grep_baseline.py` | missing |
| D5 | Corpus security scan: six evidence families over 162 documents; nine benign flags; regression test on refresh | `scripts/scan_skills.py`, `docs/CORPUS_SECURITY.md` | missing |
| D6 | Finding 6: escalation measured on 20 skills with the small model: median 22,440 tokens and $0.088 per compaction, fit 17,939 + 0.595 x characters; agent run median 80,331 tokens ($0.055); refuted configurations wasted 15.8 M tokens and $14.296 (`token_economics.json`, field `wasted_usd`) | `results/token_economics.json` | missing |

## E. Post-v11 additions (R12–R20, from the session summary; not in the v11 PDF)

| # | Item | Status |
|---|---|---|
| E1 | `principal_characterises` (k* tolerated budgets are b <= k*), `cone_is_not_degenerate`, `congruence_is_not_degenerate`, `Ggood_is_robust`, `strips_cap_cone` | missing |
| E2 | Numbers manifest: 104 numbers tied to `results/` by expression, 57 pinning their sentence; `cite` guard over 144 Coq citations; `make check` | missing |
| E3 | Cell-by-cell tests of Tables 1–3; CLI-vs-§2-block diff test | missing |
| E4 | Theorem 34 (hypothesis restored), "Both repairs" wording, timing bands in `make results` | missing (paper text) |
