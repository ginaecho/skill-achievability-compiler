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
| `../../scripts/usefulness.py`, `results/usefulness.json`, `../../docs/USEFULNESS.md` | the usefulness experiment: 162 real skills surveyed, 8 + 5 run as tasks at two input scales, 4 specification pairs, two runtimes, artifacts verified |
| `../../scripts/token_economics.py`, `results/token_economics.json`, `../../docs/TOKEN_ECONOMICS.md` | tokens with and without the checker; when LLM compaction is needed and what it costs |
| `../../scripts/scan_skills.py`, `results/security_scan.json`, `../../docs/CORPUS_SECURITY.md` | static security review of the third-party corpus (read-only; gated by `tests/test_corpus_security.py`) |
| `../../src/skillc/autollm.py` | the escalation rule (`skillc autocheck`) |
| `../../benchmarks/spec-cases/` | nine authored achievable/not-achievable pairs with mock tools; eight of the nine refutations need reachability, not a capability set-difference |
| `../../scripts/grep_baseline.py`, `results/grep_baseline.json` | the regular-expression baseline (25/34 against the checker's 34/34) |
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
  none is written: the goal survives the branch (rational choice).
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

**189 audited names (187 theorems and two constructors), every one axiom-free** (`Print Assumptions` harnesses).
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
- Severity benchmark (17 protocols, 55 branch verdicts, 0.21 s): 29 Benign / 7
  Futile / 19 Catastrophic **over all branches** — 28 of the 29 Benign are
  branches whose guard holds, so restricted to *misselections* the split is
  1/7/19; `k*` = 0 for 9, 1 for 2, ≥5 for 6; PNR actions purchase, send,
  deploy, delete, ship, purge, refund, drop_old, commit. 16/17 matched
  pre-stated expectations; the exception was a benchmark authoring error, fixed.
- Live agents (340 runs, two models, plain vs pressured, $1.59): 0 theorem
  violations; 6 of 19 Catastrophic verdicts taken by a real agent, 17 times;
  repairs remove the catastrophes. **No rate claim is supported** — 0/120 on
  the tolerant protocols is arithmetically forced, the low-`k*` counts invert,
  and 10 of the 11 misselections on tolerant protocols are one Benign branch
  whose guard the pressure prompt asserts.
- Corpus census (162 skills, 13 repositories, no model tokens, 2.1 s):
  149 certified at home, 108 refuted in a file-only runtime, 95 flip.
- Usefulness (134 agent runs over 16 documents — 8 corpus skills and 8
  specification cases): certified 67/68 verified artifacts (64 also reached the
  status line, 3 verified without it, 1 was a silent wrong result); refuted, where the
  skill's procedure is the only route, 0 verified out of 46 with 7
  fabrications; the five "computed by hand" skills reverse at realistic input
  size: 20/20 verified at a dozen rows, 0/18 at a thousand (14.3 M tokens).
- Differential testing: the analyzer and the Coq-extracted kernel agree on the
  tolerance degree for 500 of 500 random protocols across two seeds, 0
  disagreements (`scripts/differential_test.py`).
- False refutations: of 13 skills refuted in their home runtime, 6 are genuine
  and 7 are front-end misextractions, audited one by one in
  `benchmarks/home_refutation_audit.json` (4.3% of the corpus, and 46%
  precision on the refutations themselves — the number to carry).
- Corpus security: 162 documents scanned statically, no malicious skill and no
  injection payload aimed at an agent; 9 benign flags reviewed in
  `docs/CORPUS_SECURITY.md`; a test fails on any unreviewed hit.
- Token economics: escalation to LLM compaction fires on 130/162 skills at
  home and 49/162 in the file-only runtime (108 free refutations);
  median compaction 22440 tokens = 27.9% of one agent run (20 of 24
  attempts returned a pack; the other four are counted as failures).
- Modularity: the tool's own hazard decision is already linear (22 queries at
  n=6), so the like-for-like comparison is computing an *interface*: complete
  whole-system enumeration 566 queries / 22.4 s at n=6 against the projected
  modular 48 / 0.083 s; the concrete interface is worse than not abstracting
  (1149 queries, 256 points). The win that survives is re-check: 109 ms
  growing with n against 13 ms constant.

## Before submission

- Drop `anonymous`; fill authors, ORCIDs, funding, acknowledgements.
- Inline bibliography → `plainurl` + `.bib`; resolve `[to verify]` entries.
- Remove the draft banner, `WIP:` boxes, and the `DO-NOT-SUBMIT` marker.
- Interleaving of communications between disjoint role pairs and asynchronous
  buffering (the classical permutation lemma).
- Environment choices and the arithmetic fragment in the verified kernel.
- Scale the live-agent experiment (more models, more runs) if reviewers ask.

## Build

```
pdflatex main.tex && pdflatex main.tex     # needs texlive-fonts-extra
cd proof && make && make binary             # Coq 8.18 + OCaml 4.14
pip install -e ../.. && python3 ../../scripts/severity_eval.py
python3 ../../scripts/live_agents.py       # needs the Claude Code CLI
python3 ../../scripts/fetch_skills_ext.py && python3 ../../scripts/usefulness.py
python3 ../../scripts/token_economics.py --compact 24    # measures LLM compaction
```
