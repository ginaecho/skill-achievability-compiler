# MLADS+ Agents submission: revision notes (30 September 2026)

This note records how the two MLADS documents (`MLADS_AGENT_Submission.docx`,
`MLADS_supplementary.docx`) were revised after the NeurIPS 2026 VerifyAgents
reviews of the earlier manuscript, and which repository evidence each change
draws on. Nothing in the revision is new data: every number comes from
experiments already recorded in `docs/` on `main`, in `runs/` and `benchmark/`
on the branch `gc/data_train_test`, or from code on the feature branches named
below.

## What the reviewers asked for, and where it is now answered

| Reviewer point (meta-review, JaUr, ri6M, ijdA, km6X) | Main proposal | Supplement | Evidence |
|---|---|---|---|
| The LLM compaction step is never tested; no real SKILL.md; corpus is self-written and self-labelled | Data; Results "Real skills: 88% of verdicts agree with execution"; Figure 3 | 4.1, 5.5, 5.6, Figure 6, Tables 5.1–5.2 | `docs/P2G_RUNTIME_BINDING.md`, `docs/DIVERSITY_TEST.md`, `docs/P2G_GROUNDED_TEST.md`, `docs/I2L_BENCHMARK.md`; runs `20260926_heldout_*`, `20260926_tpl`, `20260927_ext`, `20260928_div`, `20261001_gr` |
| No baseline (an LLM judge; a plain planner) | Results: direct model verdict D (0.905 vs 0.893, p = 0.82, 40% of tokens) | 5.5, Table 5.2 | `docs/I2L_BENCHMARK.md`, `runs/20260928_i2l/metrics.json` |
| Name the model, give the prompt, show one complete pack | Methodology (GPT-5.4; Claude family), Listing 1 | 3.3, 3.6, Listing 1, 4.1 "Model" | `src/skillc/frontend/ce.py`, `docs/CONTROLLED_ENGLISH.md`; the listing's two verdicts were reproduced with the released checker |
| How does compaction learn the harness's tool inventory? | Methodology (runtime binder); Integration (MCP `tools/list`) | 3.6 step 1, 6.3 | `src/skillc/data/runtimes/*.json`, `src/skillc/frontend/runtime.py`; `src/skillc/mcp.py` on `feature/mcp-tool-fact-inference` |
| NON_PROJECTABLE / NON_CONFORMANT are returned as IMPOSSIBLE without a covering theorem; T-Comm requires every branch to conform | Methodology "Explain the decision" (goal-only policy); "Why the check is credible" | D.8 table and discussion; 6.1 | `src/skillc/checker.py` (`scope="goal"` turns a protocol rejection into UNKNOWN / `PROTOCOL_ONLY`) |
| The 87x saving is a cost model stated as fact | Not claimed; the main proposal reports only measured live-backend and reuse tokens | Appendix E is marked as a model, F.4 separates proxies from provider records | unchanged |
| "Decidable" in the title | Title already dropped it | — | — |
| Related work: LLM-to-PDDL, how often formalisation is wrong | Related Work [15] Planetarium, [16] LLM+P | 2, refs [20]–[21] | verified against arXiv 2407.03321 (NAACL 2025) and arXiv 2304.11477 |
| Future work "check during reasoning" (was a plan) | Integration: runtime monitor, four live scenarios | 6.2 (signals table, scenarios A–D, observed limits) | `docs/RUNTIME_MONITOR.md`, `src/skillc/monitor.py`, `runs/20260928_monitor_live/summary.json` |

## Changes to the main proposal (4 content pages + references)

- Introduction: adds the real-skill claim (490 blind-executed pairs) and the runtime monitor.
- Related Work: adds the translation-reliability point with two verified references.
- Methodology: describes Controlled English and runtime-bound compaction (P2g)
  with the guarded repair; adds Listing 1 (a complete skill; both verdicts
  reproduced); states the protocol-scope versus goal-only distinction. Figure 2
  (workflow) and Table 1 were removed from the main proposal to make room; the
  workflow figure remains Figure 1 of the supplement.
- Data: three evidence sets, the benchmark corpora, runtimes, blind-execution
  labels, pre-registration, and the direct-verdict baseline.
- Results: Figure 3 is now the real-skill benchmark (per-set dot plot with
  Wilson intervals); the per-family savings bars moved to the supplement (F.1
  and its Figure 3). New paragraph on real skills, honest about the direct
  baseline matching P2g's accuracy and about the two negative results.
- Integration: MAF paragraph shortened; new paragraph on the pre-session hook,
  MCP tool inventory and the runtime monitor.
- "Why the check is credible" now distinguishes reachability refutations
  (covered by the mechanized theorem) from protocol refutations (declared
  workflow only).
- Conclusion: future work updated (monitor benchmark, core-versus-optional,
  severity-aware typing).
- References [15], [16] added.

## Changes to the supplement

- Abstract and Section 1 map updated.
- Section 2: translation-reliability paragraph.
- Section 3.3: models named. New Section 3.6: Controlled English, the binding
  clauses, the six-step P2g procedure, round-trip guarantees.
- New Section 4.1: benchmark design (five test sets, three runtimes, labels,
  strict adjudication, pre-registration commits, metrics, baseline, model).
- New Section 5.5: per-set results (Table 5.1), JSON comparison, the
  intent-to-logical-block arms (Table 5.2), paired tests, what the block buys,
  the failed construct-validity check. New Section 5.6: generalisation across
  domains and runtimes, the policy index, the two negative results, remaining
  errors, caveats.
- Section 6: the outdated "further work will explore controlled English"
  sentence replaced. New 6.2 (runtime monitor) and 6.3 (pre-session hook, MCP
  inventory). 6.1 "Why the check is credible" revised.
- Section 8: conclusion updated.
- References [20], [21].
- New Appendix D.8: which result covers each verdict reason code, and why the
  protocol codes refute the workflow rather than the goal.
- F.4 and Appendix G updated; "Before upload" now also asks for the exact
  Claude model version of the benchmark sub-agents.

## Lemma 3: the argument was wrong in shape, and is now mechanized

The reviews said Lemma 3 (the link between Theorem 1 and the checker's
symbolic state) was on paper only. Checking it against `proof/SkillAchievability.v`
showed a sharper problem: the mechanized schema took the abstraction as a
*function* `abs : W -> A`, while Lemma 3 represents a world ⟨B,N⟩ by (B,ψ) for
*every* accumulated constraint ψ that N satisfies, where ψ depends on the search
path. That is a relation, so the lemma as written did not instantiate the
schema it claimed to instantiate.

What changed (all checked with Coq 8.18.0, the CI pin; `Print Assumptions`
reports every result closed under the global context):

- `refutation_sound_rel`: Theorem 1 restated with a simulation relation
  `R : W -> A -> Prop` (step-sim: a related abstract successor exists;
  goal-sim: relation preserves the goal). `refutation_sound_fun_is_rel` shows
  the original functional theorem is the special case `R w a := (a = abs w)`.
- `SymbolicInstance.symbolic_refutation_sound`: Lemma 3 mechanized for a
  shallow embedding of the state logic. Constraints are predicates on numeric
  worlds; guards and effects are relations; the strongest postcondition is the
  image; the widening is an arbitrary edge policy (so the back-edge policy of
  the implementation is covered); the abstraction is the relation N ⊨ ψ.
- `tests/test_proof.py` now expects eight axiom-free results from
  `check_assumptions.v`.

What still remains on paper, and is now stated as such in every place that
mentions Lemma 3: that the checker's QF-LIA formulas denote those predicates,
and that Z3 decides their satisfiability correctly. The text no longer says
"Lemma 3 is on paper"; it says exactly which refinement is.

Where the text changed: `paper/skillachievability.tex` (limitations paragraph,
Appendix D intro, the abstraction relation and Transport lemma, Lemma 3
statement and proof; all inside blue-marked `\bgc...\egc` regions, PDF not
rebuilt here because no TeX toolchain is installed), the supplement (D intro,
Lemma 3 proof tail, a new remark after it, the D.8 row, Section 6.1), the main
proposal ("Why the check is credible"), and `paper/README.md`.

## Things the authors must still confirm before upload

1. The exact Claude model version used by the compaction, execution and
   adjudication sub-agents of the real-skill benchmark. The run plans say
   "same model family" and do not pin a version; the documents say "one Claude
   model family" and flag this in Appendix G.
2. The pre-session hook and the MCP `tools/list` inference are implemented
   with tests on the branches `feature/pre-session-agent-integration` and
   `feature/mcp-tool-fact-inference`, not on `main`. The documents describe
   them as implemented; merge or cite the branch before publication.
3. The integration-repository link placeholder (unchanged from the previous
   version).
4. The severity-aware protocol typing named as future work is the working
   draft on `gc/ecoop-paper-theorems-benchmarks` (`paper/WIP`); no numbers
   from it are claimed.

## Numbers used, and how they were derived

- Pooled real-skill figures (post hoc, five sets): decided 36+38+115+164+94 =
  447 of 490; correct 29+34+103+141+87 = 394 (0.88); recall 8+12+33+38+31 = 122
  of 145 (0.84); false rejections 1+2+10+14+3 = 30 of 302 (0.10).
- Figure 3 / Figure 6 intervals are Wilson 95% computed from the counts in
  the run comparison files; the JSON and direct-verdict rows come from
  `runs/20260928_i2l/metrics.json` ("heldout+fresh" and "gr").
- Listing 1 verdicts: `skillc` on `main` with `bind_runtime` against
  `developer-sandbox` (BLOCKED_GUARD on `book_flight`) and `office-assistant`
  (MISSING_CAPABILITY on both tools).

## Rendering

The PDFs beside the Word files were rendered with LibreOffice using Carlito
(metric-compatible with Calibri). Word will reflow slightly; re-check the
four-page limit of the main proposal in Word before upload.
