# Paper-to-implementation ledger: "Affordable Mistakes"

**Status, 2026-11-04: the paper and the implementation agree.** The 28-page paper
(`paper/WIP/main.tex`) builds with 0 errors and 0 overfull boxes; all 189 Coq results are closed
under the global context; all 144 results the paper cites are defined and harnessed;
`skillc severity` prints the paper's Section 2 listing byte for byte; the extracted kernel agrees
with the analyser on 500 of 500 random protocols; and all 136 numbers in `results/CLAIMS.json`
agree with the shipped results (`make check`). The evaluation was re-run on 2026-11-03/04 with
the current haiku and sonnet models, URL-scrubbed prompts and a 157-skill corpus
(`docs/BENCHMARK_RERUN_2026-11.md`). Section 10, the abstract, C5 and the conclusion were rewritten
to what that re-run shows: Finding 4 no longer establishes non-vacuity (no agent took a
Catastrophic branch), and in Finding 5, 5 of 16 refuted realistic file-only runs still produced a
correct artifact by hand. The status column below gives the September value beside the re-run
value where they differ; the paper now states the re-run value.


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
| A1 | §2 worked instance: G_bad 0-tolerant, not 1-tolerant; narrowed is k-tolerant | `Gbad_is_0_tolerant`, `Gbad_not_1_tolerant`, `Ggood_is_k_tolerant` | present |
| A2 | Def 2 budgeted reachability | `reach_haz` | present |
| A3 | Thm 6 trichotomy ordered | `reach_mono_budget`, `severity_monotone_in_budget`, `benign_step_up`, `benign_no_regress`, `benign_step_down`, `catastrophic_upward`, `futile_downward`, `tolerance_degree_is_a_threshold`, `severity_classes_are_separated`, `reach_mu_iff_run` | present |
| A4 | Thm 7 partition | `severity_disjoint`, `severity_exhaustive` | present |
| A5 | Thm 9 exact characterisation | `TC_sound`, `TC_complete`, `TC_exact`; `tolerance_downward_closed`, `tolerance_antitone_in_ctx` | present |
| A6 | Def 10 instrumented head-move semantics | `hstep` | present |
| A7 | Thm 11 bridge | `bridge_step`, `bridge_run` | present |
| A8 | Thm 12 progress under misselection | `progress`, `every_label_steps` | present |
| A9 | Thm 13 budgets distribute over participants | `budget_distributes` | present |
| A10 | Thm 14 bridge, recursive (Mu.v: `ctypes`, `hstep`) | `sim_step`, `bridge_mu`, `bridge_finite_via_mu` | present |
| A11 | Thm 15 bystanders (Interleave.v) | `swap_safe`, `swap_ctypes`, `bridge_interleaved` | present |
| A12 | Thm 16 STRIPS variable disjointness | `strips_commute`, `strips_enables`, `strips_preserves`, `strips_neutral`, `strips_swap_act` | present |
| A13 | Thm 17 product (Regular.v) | `product_correspondence` | present |
| A14 | Thm 18 loops meet the budget | `budget_never_increases`, `dev_edges_bounded`, `dev_edges_exact` | present |
| A15 | Thm 19 decidability | `decide_reachb`, `decide_sound`, `decide_complete`, `reach_bounded_path`, `decide_reachb_correct` | present |
| A16 | Thm 20 unfolding closure finite (Mu.v: `Gr`, `reach_mu`) | `cands_closed`, `reach_in_cands`, `subst_comp`, `unfold_close` | present |
| A17 | Thm 21 embedding | `reach_embed`, `TC_regular` | present |
| A18 | Thm 22 decidability for mu-types | `decide_mu`, `decide_mu_correct` | present |
| A19 | Prop 23 tolerance degree computable, PSPACE (paper proof only) | — | n/a (paper) |
| A20 | Thm 24 modular composition | `TC_seq`, `TC_seq_interface` | present |
| A21 | §10 verified kernel (Kernel.v) | `kernel_first_spec`, `goal_reachable_correct`, `decide'_sound`, `decide'_complete`; extraction to OCaml | present |
| A22 | Thm 25 narrow | `repair_narrow_sound` | present |
| A23 | Thm 26 guarded branch futile not stuck | `validates_ab_enabled`, `reach_halted`, `safeT_halted`, `guard_abort_is_futile` | present |
| A24 | Thm 27 guard | `repair_guard_exact`, `guard_absorbs_misselection` | present |
| A25 | Thm 28 reorder | `repair_reorder_sound`, `reorder_original_exact`, `reorder_reordered_exact`, `repair_reorder_pnr` | present |
| A26 | Thm 29 compensate | `repair_compensate_sound`, `repair_compensate_restores_goal` | present |
| A27 | §11 booking instance | `Gbad2_not_1_tolerant`, `commutes_verify_purchase`, `Greordered_is_k_tolerant` | present |
| A28 | §13 refuted predecessor | `act_vacuous_with_partial_qres`, `act_vacuous_coinductive`, `taint_laundering_refutes_noninterference`, `goal_only_cycle_hits_cap` | present |
| A29 | Assumption 5 as hypothesis, never an axiom; no classical principle; `Print Assumptions` harness for every result | `check_sev.v` etc. | present |

## B. Tool (paper §2, §10)

| # | Paper statement | Artifact | Status |
|---|---|---|---|
| B1 | `skillc severity`: per-branch severity, k*, first hazard witness, point-of-no-return action, narrowing repair, bystander pairs to serialize; k_max = 4 | `src/skillc/severity.py`, CLI subcommand | present (`skillc severity`) |
| B2 | Default rational-choice guards; default hazard = irreversible action while goal lost; explicit guard/hazard overrides; declared-irreversible tools; environment-controlled choices resolved demonically | same | present |
| B3 | Output format of §2 (`migration_backup: tolerance degree k* = 1 ...` listing, incl. `keep_old Futile misselection` line, branch counts, bystander summary) | CLI; a test diffs CLI output against the paper block | present: byte-identical, tested by `test_the_papers_verbatim_block_is_the_tools_output` |
| B4 | Fifteen tests check tool verdicts on the paper's instances against the Coq development's | `tests/test_severity.py` | present (`tests/test_severity.py`) |
| B5 | `skillc severity --verified`: extracted OCaml kernel on the boolean fragment; agrees on the 16 in-fragment benchmark protocols in < 50 ms each | `proof/Kernel.v` extraction + Python elaboration (~100 lines Coq + ~100 Python) | present: `make binary`; `skillc severity --verified` |
| B6 | Differential test: random packs in the shared fragment, 499 protocols over two seeds, 0 disagreements | `scripts/differential_test.py` | present: 500/500 agree, 0 disagree over seeds 20260902 and 4242 (the final paper's figure; v11 said 499) |
| B7 | Front-end rule: a fenced code block is an invocation of the shell | front end | present |
| B8 | `skillc autocheck`: escalate to LLM compaction when the pack is weak; 130/162 escalated in home runtime, 49 in file-only | CLI subcommand | present (`skillc autocheck`); escalations 126 home, 50 file-only on 157 skills (paper 130, 49 on 162) |
| B9 | Recording pass no longer stops at the first hazardous branch (bug found by Finding 4) | severity analyser | present |

## C. Deterministic evaluation (no model tokens)

| # | Paper statement | Artifact | Status |
|---|---|---|---|
| C1 | Finding 1: 15-pack corpus, its 6-pack extension and 17 vendor skills compiled by the deterministic front end contain no irreversible effect and (the 17) no choice point; trivially tolerant | `scripts/severity_eval.py` census | present, reproduces: 38 packs, none with a choice point |
| C2 | Finding 2 / Table 1: 17 authored protocols with provenance notes stating the expected verdict before running; 55 branch verdicts: 29 Benign, 7 Futile, 19 Catastrophic; k* 9x0, 2x1, 6x>=5; total 0.33 s; one authoring error found and recorded | `benchmarks/severity/*.json` (or similar) + results | present, reproduces exactly: 55 verdicts, 29/7/19, k* 9x0 2x1 6x>=5; wall clock 0.47 s here vs 0.21 s |
| C3 | Bystander check on the two release protocols: audit release exact (five independent pairs), cache release two pairs to serialize | same | present, reproduces |
| C4 | Three pairs: repairs restore tolerance; severity property of node and world (insurance claim); PNR depends on Γ's establishers (rollback) | same | present, reproduces |
| C5 | Finding 3 / Table 2: migration segment chained n=1..6 at k=2: whole-system complete enumeration vs modular concrete exits vs modular projected (cone of influence); re-check cost after replacing last segment; deployment segment 728 ms vs 59 ms at n=6 | `scripts/severity_eval.py --chains` | present, query counters reproduce exactly (566/48/1149/22/8); wall clock 2-2.5x slower on this machine |

## D. Evaluation that needs model calls (Claude sub-agents; CLAUDE.md rules: URL-scrubbed prompts, sandbox, no credentials)

| # | Paper statement | Artifact | Status |
|---|---|---|---|
| D1 | Finding 4: live agents, two production models (small, mid), plain vs pressured, 5 runs per protocol x model x condition = 340 runs, 400 decisions; every catastrophe exceeded k*; catastrophe rate ordered by k* (0/120 on k*>=5, 7/220 on k* in {0,1}); 6 of 19 Catastrophic branches taken by a live agent; earlier prompt form re-run and reported | `scripts/live_agents.py`, `results/` | present (`scripts/live_agents.py`), re-run 340 runs, $0.63: theorem-consistency holds (0 catastrophes on tolerant protocols) but DOES NOT REPRODUCE non-vacuity: 0 of 19 Catastrophic branches taken (paper 6), 0 catastrophes at k*<=1 (paper 7) |
| D2 | Finding 5: 162 real skills (17 vendor + 145 third-party, 12 repos, de-duplicated by hash, provenance recorded), two runtimes; 149 certified at home, 108 refuted file-only, 95 flip, 13 refuted at home; hand audit of the 13 (6 genuine, 7 misextractions = 4.3 % false refutation); census 1.8 s | `benchmarks/home_refutation_audit.json`, census script | present; census on 157 skills: 143 certified, 103 refuted file-only, 89 flip, 14 refuted at home (6 genuine, 8 misextraction incl. astropy, new upstream); false-refutation 4.5% (paper 4.3%) |
| D3 | Finding 5 / Table 3: 134 verified runs (8 real skills x 2 runtimes x 2 models x 2 runs; 9 spec pairs A/B; 5 skills at realistic scale); artifact verification by recomputation; costs and tokens per row | `benchmarks/spec-cases/`, run harness, verifiers | present, re-run 136 runs, $7.60: certified 68/76 verified, 1 silent wrong; DOES NOT REPRODUCE the realistic file-only result: 7 of 20 refuted runs produced a verified artifact (paper 0 of 18); realistic task file reconstructed (never committed in September) |
| D4 | Grep baseline: 25 vs 34 on the 34 independently-known configurations, 0.2 ms | `scripts/grep_baseline.py` | present, re-run: grep 22, checker 32 of 34 (paper 25 and 34) |
| D5 | Corpus security scan: six evidence families over 162 documents; nine benign flags; regression test on refresh | `scripts/scan_skills.py`, `docs/CORPUS_SECURITY.md` | present, re-run: 157 documents, 8 flagged, 1 new hit reviewed benign |
| D6 | Finding 6: escalation measured on 20 skills with the small model: median 22,440 tokens and $0.088 per compaction, fit 17,939 + 0.595 x characters; agent run median 80,331 tokens ($0.055); refuted configurations wasted 15.8 M tokens and $14.296 (`token_economics.json`, field `wasted_usd`) | `results/token_economics.json` | present (both manifest fields now computed), re-run: median 10,711 tokens, $0.003 per compaction (paper 22,440, $0.088); 24.9% of a median run (paper 27.9%); refuted runs wasted $2.53 (paper $14.296) |

## E. Post-v11 additions (R12–R20, from the session summary; not in the v11 PDF)

| # | Item | Status |
|---|---|---|
| E1 | `principal_characterises` (k* tolerated budgets are b <= k*), `cone_is_not_degenerate`, `congruence_is_not_degenerate`, `Ggood_is_robust`, `strips_cap_cone` | present |
| E2 | Numbers manifest: 104 numbers tied to `results/` by expression, 57 pinning their sentence; `cite` guard over 144 Coq citations; `make check` | present: `make check` / `check_paper_numbers.py`, 104 claims, 144 citations |
| E3 | Cell-by-cell tests of Tables 1–3; CLI-vs-§2-block diff test | present |
| E4 | Theorem 34 (hypothesis restored), "Both repairs" wording, timing bands in `make results` | present (restored main.tex, 28 pages, body ends p. 25) |
