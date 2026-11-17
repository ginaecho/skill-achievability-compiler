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
| `proof/Regular.v` | **(B)** regular protocols: product, loop/budget lemma, pigeonhole, executable decision procedure over a successor-closed node list (8) |
| `proof/Mu.v` | **(B')** μ-types: unfolding as substitution, the unfolding closure is finite and step-closed, the finite fragment embeds, the bridge for recursive sessions, `decide_mu` sound+complete (10) |
| `proof/Interleave.v` | bystander interleavings: the swap relation, `swap_safe`, `swap_ctypes`, `bridge_interleaved`, and the STRIPS variable-disjointness condition `strips_*` (10) |
| `proof/Kernel.v`, `proof/extract.v`, `proof/kernel/` | the verified kernel: `decide_mu` on bit-vector worlds, `kernel_first_spec`, `goal_reachable_correct`; extracted to OCaml, driven by `skillc severity --verified` (3) |
| `proof/Repairs.v` | guard, reorder, compensate (narrow is in Severity.v): soundness, exact characterizations, the point-of-no-return theorem, a worked instance (13) |
| `proof/DeviationLayer.v` + `proof/AUDIT.md` | the mechanized audit that refuted the predecessor draft (14) |
| `results/severity.json` | **(C)** raw evaluation output |
| `results/live_agents.json`, `results/live_agents_runs.jsonl` | the live-agent experiment (every run, every reply) |
| `../../docs/LIVE_AGENTS.md` | live-agent tables |
| `../../scripts/live_agents.py` | the live-agent experiment (`claude -p`, no tools) |
| `../../scripts/usefulness.py`, `results/usefulness.json`, `../../docs/USEFULNESS.md` | the usefulness experiment: 157 real skills surveyed, 8 + 5 run as tasks at two input scales, 4 specification pairs, two runtimes, artifacts verified |
| `../../scripts/token_economics.py`, `results/token_economics.json`, `../../docs/TOKEN_ECONOMICS.md` | tokens with and without the checker; when LLM compaction is needed and what it costs |
| `../../scripts/scan_skills.py`, `results/security_scan.json`, `../../docs/CORPUS_SECURITY.md` | static security review of the third-party corpus (read-only; gated by `tests/test_corpus_security.py`) |
| `../../src/skillc/autollm.py` | the escalation rule (`skillc autocheck`) |
| `../../benchmarks/spec-cases/` | nine authored achievable/not-achievable pairs with mock tools; eight of the nine refutations need reachability, not a capability set-difference |
| `../../scripts/grep_baseline.py`, `results/grep_baseline.json` | the regular-expression baseline (22/34 against the checker's 32/34) |
| `../../scripts/llm_judge_baseline.py` | the LLM-judge baseline (scripted; the model calls did not complete in this environment) |
| `../../real-skills-ext/PROVENANCE.json`, `../../scripts/fetch_skills_ext.py` | the 28 third-party skills (re-fetchable; files not committed) |
| `../../docs/SEVERITY_RESULTS.md` | evaluation tables |
| `../../src/skillc/severity.py` | the implementation (`skillc severity <pack.json|SKILL.md>`) |
| `../../src/skillc/data/severity_corpus.json` | the 17-protocol severity benchmark with pre-stated expected verdicts |
| `../../scripts/severity_eval.py` | the evaluation, including the modularity experiment |
| `../../tests/test_severity.py` | tool verdicts checked against the Coq instances |
| `NOVELTY.md`, `NOVELTY-v2.md` | prior-art audits (withdrawn draft; current design) |
| `notes/` | design notes |

## The core idea

- **Guarded choice**: each branch carries the predicate making it *intended*;
  taking a branch whose guard fails is a **misselection**. Default guard when
  none is written: the goal survives the branch; once the goal is lost from
  every branch, the hazard stays avoidable from it; if no branch avoids the
  hazard, every branch (a forced choice is free).
- **Severity**: `Benign` (goal still reachable), `Futile` (goal lost, nothing
  harmed), `Catastrophic` (hazard reachable). *Failure is not disaster.*
  The classes are **ordered**: severity is monotone in the budget along
  Futile < Benign < Catastrophic, so they are three consecutive intervals and
  `k*` is a genuine threshold; and `Catastrophic` means an affordable **run**
  reaches harm (`reach_mu_iff_run`), not merely that a predicate holds.
  Default hazard: an irreversible tool fires after the goal is lost.
  `Benign` is a **possibility**, not a guarantee: `Robust` is the universal
  reading (every affordable misselection and every environment answer still
  arrives at the goal), it implies `Benign` (`robust_benign`), and the
  implication is strict (`benign_is_not_robust`). The tool reports `Benign`.
- **k\* is principal**: the tolerated budgets are exactly those `<= k*`
  (`principal_characterises`), `k*` is unique (`principal_unique`) and exists
  whenever tolerance is finite (`principal_exists`), which is what licenses
  computing it by a scan.
- **k-misselection tolerance**: no run with ≤ k misselections reaches a hazard.
  Possibilistic — no probabilities. The tolerance degree `k*` is the headline.
- **T-Choice-Safe**: exact syntax-directed characterization.
- **Non-vacuity**: every two-role protocol is inhabited, over any runtime in
  which a tool call always has an answer --- `canon` reads the global type as
  a pair of processes and `canon_conforms` proves it conforms in every world,
  so the bridge is never a guarantee about an empty class. Explicit sessions
  are also exhibited for the worked instances and for the repairs.
- **Bridge**: a session typed against a k-tolerant protocol is hazard-free
  within budget k; budgets distribute over participants; holds for recursive
  sessions and protocols (`bridge_mu`).
- **Regular protocols**: the μ-unfolding closure is finite (`cands_closed`),
  the finite fragment embeds (`TC_regular`), `decide_mu` is sound and complete.
  The recursive layer has its **own judgment**, `safeR` --- T-Choice-Safe read
  coinductively --- exactly non-reachability (`TR_exact`), a conservative
  extension of the finite one (`TC_is_TR`), decided by `decide_mu`
  (`decide_mu_judgment`) and consumed by the bridge (`bridge_mu_safeR`).
  **Guardedness** is mechanized and is needed in exactly one place: progress.
  `μX.X` is typable (conformance is coinductive), unfinished and permanently
  stuck (`contractiveness_is_necessary`); `progress_mu` holds under `gd`;
  the decision procedure needs no guardedness at all.
- **Environment choices** (`EnvSeverity.v`, `EnvBridge.v`, `EnvRegular.v`): a
  choice the environment controls costs no budget and is existential for the
  hazard (RH-Env, T-Env: `env_reach_iff`, `env_typing_iff`). A conservative
  extension (`safe_embedE`) re-proves exactness (`TE_exact`), T-Sub, the
  ordered trichotomy with the goal read demonically over the environment
  (`severityE_monotone_in_budget`, `env_goal_is_demonic`), k\* principal, the
  default guards (`dguard_some_intended`), the bridge for every resolution of
  the environment (`bridgeE_run`), the product and decision procedure
  (`decide_env_correct`) and, for the hazard question, μ-types
  (`decide_mu_env_correct`, `bridge_mu_env`, `TE_is_TR`). A policy-shaped
  instance has k\* = 0, is tolerant at every k once the rule is a
  precondition (`Gpol_kstar_is_0`, `Genf_is_k_tolerant`), and with an
  execute/hold choice after the user's answer stays at k\* = 0 under
  enforcement and becomes tolerant under narrowing
  (`Gconf_enforced_kstar_is_0`, `Gconf_narrowed_is_k_tolerant`). Not covered:
  the demonic goal and default guards at the μ layer, composition, the cone,
  bystanders and repairs with environment choices, and the kernel.
- **Repairs**: narrow, guard, reorder, compensate --- all proved sound;
  guard and reorder characterized exactly, in an **aborting** model where the
  validation always fires and a failed check diverts to an *inert* world
  (everything enabled, nothing changes). `Abort.v` builds a runtime with such
  worlds and provably no halted one, and exhibits a session that conforms to
  the repaired protocol. The condition is a **congruence** for one-hole
  contexts (`safeT_congruence`), so all four repairs apply at nested positions,
  which is where the tool applies them.
- **Bystanders**: every permutation of independent nodes (actions under
  semantic independence, communications between disjoint role pairs
  unconditionally) preserves the condition and typing; variable disjointness
  of STRIPS footprints discharges the action conditions, which is what the
  tool checks.
- **Verified kernel**: on the boolean fragment the tool's k* is cross-checked
  against a decision procedure extracted from the proof (16/16 agree). The
  kernel's goal notion is the stronger one --- it requires the protocol to run
  to completion (`goal_reach_implies_reach_mu`, `goal_reach_strictly_stronger`)
  --- so the cross-check is evidence about `k*` and the hazard, not about the
  severity labels.
- **Cone of influence**: worlds agreeing on the variables the remaining
  protocol reads are interchangeable at every budget (`safeT_cone`), so a
  modular interface needs one representative per class
  (`interface_projection`). This is what makes the projected column of the
  modularity experiment sound.

## Verified results — `make` in `proof/`

**267 audited names (265 theorems and two constructors), every one axiom-free** (`Print Assumptions` harnesses).
`make binary` extracts the kernel and builds `proof/kernel/skillc_kernel`.

`make check` at the repo root verifies both of the paper's mechanical
claims: that every number Section 10 states still matches `results/`
(`results/CLAIMS.json` is the manifest; `scripts/check_paper_numbers.py`
evaluates it), and that every Coq result the paper cites exists and is
covered by a `Print Assumptions` harness. `make results` regenerates the
token-free half of the evaluation; the model-dependent runs ship as recorded.

`proof/STATEMENTS.md` lists the Coq statement of every result the paper
cites, so a reader can check that each one says what the paper says it says
without opening the sources. `python3 scripts/check_paper_citations.py` checks
that every citation resolves and is covered by a harness (a test runs it);
`python3 scripts/dump_statements.py` regenerates STATEMENTS.md.

## Evaluation headline (`python3 scripts/severity_eval.py`)

- Existing corpora (15 + 6 achievability packs, 17 real skills): **no
  irreversible effects, and the real skills have no choice points** — the
  question is invisible to them.
- Severity benchmark (17 protocols, 55 branch verdicts, 0.21 s): 35 Benign / 3
  Futile / 17 Catastrophic **over all branches** — 34 of the 35 Benign are
  branches whose guard holds, so restricted to *misselections* the split is
  1/3/17; `k*` = 0 for 9, 1 for 2, ≥5 for 6; PNR actions purchase, send,
  deploy, delete, ship, purge, refund, drop_old, commit. 16/17 matched
  pre-stated expectations; the exception was a benchmark authoring error, fixed.
- Real protocols (`../../benchmarks/severity_real/`): 18 protocols ported from
  public sources --- 6 from public agent configurations (awesome-copilot
  customisation files, Anthropic's public skills), 12 from the tau-bench and
  tau2-bench airline, retail and telecom policies --- each pre-registered
  (PROVENANCE.md and EXPECTED.md committed before the tool ran). All 1114 branch
  verdicts, every k* and every point of no return matched; all 18 have k* = 0.
  Rules the source tool enforces make a wrong choice Benign/Futile, rules stated
  only in the policy make it Catastrophic. Enforcing the policy-only rules as
  tool preconditions: k* >= 5 for 9 of 18; the other 9 stay at 0 only because of
  the user-confirmation step; narrowing: all 18 tolerant (`REPAIRS.md`).
- Live agents (3500 runs, haiku and sonnet, 35 protocols, five conditions,
  ungated and gated, $11.57; `scripts/live_agents_summary.py` writes
  `results/live_agents_summary.json`): informed conditions, authored
  protocols, 0 of 680 ungated runs entered a Catastrophic branch; real
  protocols, 68 of 720 ungated against 0 of 720 gated (1 completed
  catastrophe); misinformed, completed catastrophes 53 of 180 ungated against
  0 of 180 gated on the real protocols, 9 of 170 against 0 on the authored ones;
  0 theorem-consistency violations in every cell.
- Base discipline (achievability, not severity): census of 157 skills, 14
  refuted even at home, 6 of them genuine on hand audit; 136 agent runs over 16
  documents: certified 68/76 verified artifacts; at realistic input size 5 of 16
  refuted runs computed the artifact by hand. Full data in
  `../../docs/USEFULNESS.md`, `../../docs/TOKEN_ECONOMICS.md` and
  `../../docs/CORPUS_SECURITY.md`.
- Differential testing: the analyzer and the Coq-extracted kernel agree on the
  tolerance degree for 500 of 500 random protocols across two seeds, 0
  disagreements (`scripts/differential_test.py`).
- Modularity: the tool's own hazard decision is already linear (23 queries at
  n=6), so the like-for-like comparison is computing an *interface*: complete
  whole-system enumeration 1536 queries / 91.9 s at n=6 against the projected
  modular 48 / 0.222 s; the concrete interface is worse than not abstracting
  (2091 queries, 496 points). The win that survives is re-check: 351 ms
  growing with n against 36 ms, not growing.

## Before submission

- Run `make check` from the repository root: it fails if any number the paper
  states has drifted from `results/`, if a sentence no longer contains the
  figure it quotes, or if a `\coqok` name is not a proof covered by a harness.
- `make results` regenerates the token-free half (census, differential
  campaign, grep baseline, security scan, token economics) in about eight
  minutes here and no model tokens. Re-running it reproduced every verdict,
  count and cost in `results/` exactly; only the wall-clock timings moved, by
  up to a quarter, which is why the manifest checks those proportionally and
  everything else exactly. The model-dependent results (live agents,
  usefulness runs, LLM compaction) ship as recorded.
- Drop `anonymous`; fill authors, ORCIDs, funding, acknowledgements.
- Inline bibliography → `plainurl` + `.bib`.
- Interleaving of communications between disjoint role pairs and asynchronous
  buffering (the classical permutation lemma).
- Environment choices and the arithmetic fragment in the verified kernel.
- Scale the live-agent experiment (more models, more runs) if reviewers ask.

## Build

```
make -C ../.. check                        # numbers and Coq citations
pdflatex main.tex && pdflatex main.tex     # needs texlive-fonts-extra
cd proof && make && make binary             # Coq 8.18 + OCaml 4.14
pip install -e ../.. && python3 ../../scripts/severity_eval.py
python3 ../../scripts/live_agents.py       # needs the Claude Code CLI
python3 ../../scripts/fetch_skills_ext.py && python3 ../../scripts/usefulness.py
python3 ../../scripts/token_economics.py --compact 24    # measures LLM compaction
```
