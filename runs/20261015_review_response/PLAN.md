# Review response: plan, pre-registered 2026-10-15

Written before any model call of these experiments. The reviews of the VerifyAgents
submission (meta-review and reviewers JaUr, ri6M, ijdA, km6X) left five points open.
This plan says what is run for each, on which data, with which metrics and criteria.
Nothing here is a resubmission; the goal is that the next reviewers do not have these
questions.

## The five points

| # | reviewer point | work |
|---|---|---|
| 1 | NON_PROJECTABLE / NON_CONFORMANT returned as IMPOSSIBLE without a covering theorem; T-Comm fails on one bad branch even when another branch reaches the goal | the verdict reports goal reachability and protocol typing as two dimensions; each stamped with the formal result that covers it; hosts allow only `admissible` plans. No experiment; code, tests and `docs/VERDICT_COVERAGE.md` |
| 2 | compaction never evaluated: no cross-sample agreement, no schema-gate pass rate, no fidelity check against the source skill | experiment R (reliability) below |
| 3 | no baseline: an LLM judge, and a plain planner on the capability layer alone, on the same set | experiment R, arms D, P and T |
| 4 | the 87x and 12.2K figures are a cost model stated as fact | experiment C (measured cost) below; `docs/TOKEN_ECONOMICS.md` leads with measured numbers and labels every modelled one |
| 5 | host evidence (Agent 365, Scout, Agent Framework) rests on authored packs, not natural-language input | experiment H (hosts end to end) below |

## Experiment R: compaction reliability and baselines

**Test set.** `benchmark/claude_env/set2`: 100 real documents (70 SKILL.md, 30 agent.md)
from public repositories, pinned by commit and sha256, drawn by seed 20261004 and disjoint
from every development set. Ground truth: `set2/truth/*.json`, written blind by annotators
who listed each document's hard requirements and verified each by read-only probes inside a
Claude Code cloud session (31 BLOCKED, 69 ACHIEVABLE). The set has been used once, to score
the deterministic reader (`skillc reach --claude`, commit 5c6fe79d). **No LLM compaction has
ever run on it, and no prompt was written after reading it.** The LLM arms are therefore blind
on this set. The truth labels are requirement-availability labels, not execution outcomes:
they say whether every hard requirement of the document is available in that session, not
whether an agent completed the task. We say so wherever the numbers appear.

**Runtime.** A new manifest `claude-code-cloud` transcribes the session the truth was
verified in: its tool list (`benchmark/claude_env/session/tools.json`), its connectors, its
egress allow-list (pypi, npm, GitHub, Ubuntu, NuGet, Go proxy open; other hosts refused), no
GPU, no Docker daemon. Every arm receives this manifest and nothing else about the session.

**Arms.**

| arm | what | model | samples |
|---|---|---|---|
| P2g | runtime-bound Controlled English compaction, parse, bind, check (the method) | gpt-5.4 | 5 per document |
| P2g-x | the same, a different model family, for cross-model agreement | DeepSeek-V4-Pro | 1 per document |
| D | direct verdict: the model reads the document and the manifest and answers ACHIEVABLE / IMPOSSIBLE / UNKNOWN; no pack | gpt-5.4, DeepSeek-V4-Pro | 1 per document each |
| P | planner only: STRIPS forward reachability of the goal over the bound capabilities, ignoring protocol order, roles and typing (on P2g's packs) | none | per pack |
| T | tool lint: IMPOSSIBLE iff a Tool is bound to a runtime tool the manifest lacks (on P2g's packs) | none | per pack |
| skillc | the full checker on P2g's packs (two-dimensional verdict after point 1) | none | per pack |

P and T exist to show what each layer adds. If skillc is not more accurate than P on this set,
the protocol layer buys nothing for verdict accuracy here, and we say so.

**Metrics.**

- Schema-gate pass rate: valid on first reply; valid after one located-error retry.
- Verdict accuracy against truth, per arm, decided cases only, with Wilson 95% intervals;
  recall of BLOCKED; false refutations of ACHIEVABLE documents. UNKNOWN is reported, never
  scored as right or wrong.
- Cross-sample agreement (P2g, 5 samples): fraction of documents where all 5 verdicts agree;
  Fleiss' kappa over verdicts; mean pairwise Jaccard of Tool names; mean pairwise Jaccard of
  goal atoms; fraction where the IMPOSSIBLE witness (missing runtime tool or resource) is the
  same.
- Cross-model agreement: P2g (sample 0) against P2g-x, Cohen's kappa.
- Paired comparisons (exact McNemar): skillc vs D, skillc vs P, P2g vs P2g-x, gpt-5.4 D vs
  DeepSeek D.
- Fidelity (blind judge): for sample 0 of every document, a judge of a different model family
  (Claude, via this session's sub-agents) reads the source document and the pack rendered as
  Controlled English and scores, without seeing any verdict or truth label:
  F1 no invented Tool (every Tool corresponds to an instruction);
  F2 no omitted mandatory step;
  F3 the Goal states the document's deliverable;
  F4 no invented ordering (every protocol order is stated or implied by the document);
  F5 bindings plausible (each `via` names a runtime tool that can perform the Tool).
  Each item is yes / no / unclear with a one-line reason. A second judge scores 20% of the
  items; agreement and Cohen's kappa are reported.

**Pre-registered criteria.**

- R1: schema-gate pass after retry >= 0.95.
- R2: all-five-agree rate >= 0.80 and Fleiss' kappa >= 0.6.
- R3: false refutations (truth ACHIEVABLE, skillc IMPOSSIBLE) <= 10% of ACHIEVABLE documents.
- R4: skillc decided accuracy within 5 points of D, or better. If D is better by more than
  5 points, we report that the pack does not buy accuracy and that the case for it rests on
  the witness and the deterministic re-check, as the I2L benchmark already concluded.
- R5: fidelity F1 and F4 >= 0.85 yes. These are the two the reviewers named (invented
  steps, invented ordering).

Each criterion is reported met or not met. Nothing is tuned on this set; a method change
after seeing these results needs a new blind set.

## Experiment C: measured cost

**Question.** What does a refutation save, measured, not modelled?

**Set.** The 31 BLOCKED documents of set2 and 31 ACHIEVABLE documents matched by hash order.

**Arms.** (a) ungated run: gpt-5.4 asked to carry out the document's task in the
`claude-code-cloud` runtime in a bounded simulation (real model calls, tool results
simulated by a fixed stub that reports the runtime's manifest truthfully: a tool the manifest
lacks fails, a reachable host answers, an unreachable one is refused), at most 12 turns, stop
on achieved / blocked / impossible; (b) gated: P2g compaction once, metered by the API's own
usage block, and the checker (zero tokens).

**Metrics.** Provider-reported input and output tokens per run, per arm, medians and
bootstrap intervals; the ratio of (a) to (b) on BLOCKED documents; the overhead of (b) on
ACHIEVABLE documents relative to one (a) run. Every number is labelled "real model calls,
simulated tool results". The cost model in `src/skillc/tokens.py` stays, labelled as a model,
and the document shows how far its defaults are from the measured medians.

**Criteria.** None to pass; the point is the label. We report whether the measured ratio on
BLOCKED documents is above or below the modelled 87x, and by how much.

## Experiment H: hosts end to end

**Agent 365.** For each of the ten cases in `examples/agent365-cases`, the natural-language
`intent.md` is compacted by gpt-5.4 (3 samples) against a manifest built from the case's
`environment.json` grants and contracts. Each static check in `checks.json` (remove a grant,
replace a contract, add a dynamic spawn, etc.) is applied to the compacted pack exactly as
`run_cases.py` applies it to the authored pack. Metric: agreement of verdict and reason with
the check's expectation, per check and per sample; disagreements listed with cause
(compaction error, vocabulary mismatch, or a real difference).

**Microsoft Agent Framework.** The six role skills of `examples/hosted-agent-finance/skills`
(and the coordinator instructions) are compacted by gpt-5.4 (3 samples) into one protocol
pack in Controlled English. The gate runs with the compacted pack in place of the authored
`protocol/quarterly_finance_report.ce` against `azure.yaml`, `azure.search.yaml`,
`azure.isolated.yaml` and the email variant. Metric: agreement with the authored pack's gate
labels, and with the expectations in `tests/test_gate.py`; a false IMPOSSIBLE on a correct
configuration is reported first. This is the "we wrote the pack" threat of
`docs/HOSTED_AGENT_EVALUATION.md`, stage S-E, run offline.

**Microsoft Scout.** The 70 SKILL.md of set2 are compacted by gpt-5.4 (1 sample) against the
`scout-desktop` manifest. Metrics: verdict distribution, reasons, and the fidelity judge on a
random 20 (same rubric as R). No truth labels exist for this runtime; no accuracy is claimed.

## What is not done, and why

- No blind execution of new skills on this machine: the earlier execution labels were made
  in isolated cloud sandboxes; this workstation holds live GitHub and Azure credentials, so a
  blind executor following arbitrary public skills here is not safe. Labels in R are
  requirement-availability labels verified by read-only probes.
- No live deployment of the finance agent: experiment H is the offline gate stage; the live
  arms of `HOSTED_AGENT_EVALUATION.md` remain future work.
- One compaction model family carries most arms (gpt-5.4); a second family (DeepSeek) is
  used for agreement, and a third (Claude) for judging, so no family both writes and judges.

## Provenance

Every prompt and reply is written to disk under `runs/20261015_*` with a sha256 manifest
(`frozen.json`) before scoring; scoring is deterministic and re-runnable. Model deployments:
Azure AI Foundry resource `foundary-tzuc06`, deployments `gpt-5.4` (version 2026-03-05) and
`DeepSeek-V4-Pro` (2026-04-23).

## Addendum A (2026-10-15, after the first H results, before any new model call)

The Agent 365 part agreed on 189/189 checks, but the manifest handed the model the exact
state names and the environment contracts replaced every compacted tool definition, so the
checks could only see the step set. All 30 compacted packs also collapsed the authored
Reviewer and Triage/Fraud roles into one `agent`, which no check detects. Two additions,
fixed here before they run:

- **A365 blind-vocabulary arm.** Same ten intents, 3 samples, gpt-5.4, but the manifest's
  tool descriptions carry only the action text (no "Establishes `<state>`" and no state list),
  and the runtime description does not name any state. Alignment is by `via` only. Metric:
  the same checks; the number of packs whose goal or preconditions fall outside the
  environment vocabulary (`unaligned`) is reported, and every disagreement is classed as in H.
  Criterion: none; this arm measures how much of 189/189 was the vocabulary.
- **Separation-of-duty checks.** A new static check kind for the authored cases whose source
  describes an approver or a second agent (Genspark: Reviewer approves before the document is
  created; Celonis: Triage hands off to Fraud): the approving or second-stage action must be
  owned by a role different from the role that performs the action it gates. Authored packs
  must pass; the 30 compacted packs of the first arm and the blind-vocabulary arm are
  re-scored against the new checks without new model calls. Expected: the compacted packs
  fail these checks, which makes the role collapse visible in the agreement number.

## Addendum B (2026-10-15, after experiments C and H, before experiment R's scores were read)

Experiment C's gated arm falsely refuted 17 of 31 ACHIEVABLE documents of set2, and the
Agent Framework part of H refuted 6 of 9 correct configurations. Reading the refuted packs
(runs/20261015_cost/main/gated, runs/20261015_hosts/maf/outputs) gives six defect classes,
all in compaction, none in the checker:

| id | defect | example |
|---|---|---|
| D1 | a fact the environment or the user decides (what kind of project this is, whether an input was provided) is written as a `requires` on a Tool, and no Tool adds it | c045 `next_line_app`, c073 `firmware_available`, c002 `expo_or_eas_work` |
| D2 | the deliverable is text the agent writes in its reply; rule 9 says writing text is not a Tool, so the Goal atom has no establisher | c013 `sop_documented` |
| D3 | message receipt written as a predicate (`*_received`); `tells` steps have no effects, so nothing establishes it | finance s0 |
| D4 | branch labels, notifications or intermediate states in the Goal | finance s1, c002 `goal_classified` |
| D5 | a hosted agent's role tools bound `via mcp` / `via search` because the model saw the whole runtime manifest, not the tools the project declares | finance s0 |
| D6 | long multi-role documents break the Controlled English grammar twice (first reply and the single retry) | finance s2 |

**Fixes (compaction v2, "P2g+"), fixed here before implementation:**

- F-a. Controlled English and pack schema: an observed choice branch may state facts it
  establishes, `branch \`x\` (assuming \`p\`, \`q\`)`, stored as
  `choice.assumes[label] = [p, q]`; the checker adds them to the world when the branch is
  taken. The refutation guarantee is unchanged: the facts are declared in the pack. Prompt
  rule: environment-decided facts go on the branch, never as a Tool `requires` that no Tool
  adds. Addresses D1.
- F-b. Universal runtime tool `reply` ("the agent's own answer in the conversation"), granted
  in every manifest by the binder. Rule 9 amended: a deliverable written in the reply is one
  Tool `via reply` that adds the Goal atom. Addresses D2.
- F-c. Prompt rules: `tells` carry no effects, never write `*_received` as `requires`; the
  Goal names only the deliverable. Addresses D3, D4.
- F-d. Hosted-agent compaction receives the effective runtime (`gate.effective_runtime`,
  the manifest reduced by azure.yaml), and the gate gains `--compact` to produce the pack from
  the skills. Addresses D5.
- F-e. Two located-error retries instead of one. Addresses D6.

**Validation set.** `benchmark/claude_env/set3`: 100 documents drawn with seed 20261005,
disjoint from sets 1 and 2 (`select_cases.py --exclude` both), labelled blind by ten
annotators (Claude sub-agents, ten documents each) against the `claude-code-cloud` manifest
using `set3/RUBRIC.md`. These are judgement labels against the manifest text, not probe-
verified labels: weaker than set2's, and said so wherever they are used. No compaction has
run on set3; the annotators did not see skillc.

**Arms on set3.** P2g (the method as frozen for experiment R) and P2g+ (F-a..F-c, F-e),
gpt-5.4, 3 samples each; the direct-verdict baseline D once. Same metrics as experiment R.
Fidelity judge on 30 documents per arm (sha256("set3-judge:"+case) order), same rubric,
second judge on 20%.

**Multi-role validation.** The finance agent (F-d, three samples, gate under the three
correct configurations and the email variant), and `examples/hosted-agent-finance-group`
as a second multi-role case not used in developing the fixes.

**Criteria.**
- B1: false refutations of ACHIEVABLE documents at most half of P2g's on set3 (same samples
  compared, exact McNemar).
- B2: recall of BLOCKED documents not more than 5 points below P2g's.
- B3: fidelity F1 and F4 yes-rates higher than P2g's on the same 30 documents.
- B4: finance agent: zero false IMPOSSIBLE on the three correct configurations in at least
  two of three samples, and the email variant refuted naming the missing connection.
Each is reported met or not met. If B1 fails, P2g+ is not adopted as the default.

**Amendment to Addendum B (same day, after Addendum A's results, before set3 ran).** Addendum A
showed a seventh defect: D7, documents that name distinct actors (an approver, a reviewer, a
second agent) are compacted into one role `agent`, so every separation-of-duty check fails
(0/12 compacted packs against 2/2 authored). Fix F-f, added to P2g+: prompt rule (14), when the
document names distinct actors, declare one Role per actor and keep each Tool's owner as the
document states; never give the approving or reviewing action to the role whose action it
gates. The A365 blind-vocabulary result (0/195 verdicts, all `unaligned`) is a vocabulary
limitation of environment contracts, not a compaction fix; it stays as reported.

## Addendum C (2026-10-15, after experiment R's scores, before any set3 model call)

Experiment R met none of R1..R4. The largest miss is recall: skillc on P2g packs caught 7 of
31 BLOCKED documents, the direct verdict 29 of 31. Reading the packs: the model binds the work
to `bash` and does not write `needs` for the refused host, the missing GPU or the absent
account (defect D8). The repository's deterministic requirement reader (`skillc intent`,
`env/nl.py`) extracts exactly those requirements with the line they come from, and scored
86/100 on sets 1 and 2 against a live session. It has no manifest-only evaluation.

**Fix F-g, fixed here before implementation.** A deterministic evaluation of an intent's
requirements against a runtime manifest: hosts against a structured egress allow-list in the
manifest, programs against the manifest's software mode and a list of programs it states are
unavailable, credentials and accounts against grants, MCP servers and frontmatter tools
against the manifest's tools and connectors. A hard (non-optional) requirement that evaluates
unavailable is a deterministic refutation with the requirement and its evidence line as the
witness, reason `REQUIREMENT_UNAVAILABLE`. Manifest fields are additive (`egress_allow`,
`unavailable_programs`); manifests without them evaluate hosts and programs as unknown, never
as unavailable, so the addition can only add refutations where the manifest is explicit.

**Arms on set3**, replacing the arm list of Addendum B: P2g; P2g+ (F-a..F-f); Rdet (the
deterministic reader against the manifest, no model); P2g+ ∪ Rdet (IMPOSSIBLE if either
refutes, the witness from whichever did); D (direct verdict). gpt-5.4, 3 samples for the two
compaction arms, 1 for D. Metrics as in R, plus the per-arm recall of BLOCKED documents.

**Criteria added.**
- C1: recall of BLOCKED for P2g+ ∪ Rdet at least D's recall minus 5 points on set3.
- C2: false refutations of ACHIEVABLE documents for P2g+ ∪ Rdet at most 10%.
- C3: Rdet alone has zero false refutations on documents whose truth lists no unavailable
  hard requirement (it reads the same evidence the annotators read, so a false refutation is
  a reader bug, reported as such).
Criteria B1..B4 of Addendum B stand. Nothing is tuned on set3; a change after reading its
results needs a new set.

**Amendment to Addendum C (same day, after the P2g+ smoke test, before any set3 model call).**
The smoke test on the four motivating set2 documents fixed three; the fourth (c073) produced
no valid document in three attempts because the model wrote `requires` six times and `needs`
twice on one Tool line, which grammar 1.3 rejects (defect D6). Fix F-h: the Controlled
English parser accepts repeated `requires`, `needs`, `adds`, `deletes` and `runs` clauses on
one Tool and merges them (conjunction for `requires`, union for the lists); the renderer still
emits one clause each, so canonical documents are unchanged and the round-trip property holds.
This is parser tolerance, deterministic, and applies to both arms (P2g and P2g+) at parse time.

## Results pointer

Added after the runs; the pre-registered text above is unchanged. Experiment R:
`runs/20261015_reliability/` (fidelity judge in `judge/`), written up in
`docs/COMPACTION_RELIABILITY.md`. Experiment C: `runs/20261015_cost/`, in
`docs/TOKEN_ECONOMICS.md`. Experiment H: `runs/20261015_hosts/`, in `docs/HOSTS_E2E.md`. Set3 validation of Addenda B
and C (P2g, P2g+, Rdet, P2g+ ∪ Rdet, D): `runs/20261015_set3/` (B3 judge items in `judge/`),
in `docs/COMPACTION_RELIABILITY.md`, section "set3: P2g against P2g+".

## Addendum D (2026-10-15, after the set3 results; before any Decision-1 call): a decision model on the compaction layer

**Model.** `Microsoft-Decision-1`, deployed as `Decision-1` on `foundary-tzuc06` (GlobalStandard,
50 requests/minute, 32,768-token context). It is not a generative model: a request carries a
`state` (text or JSON) and typed questions (`noul` yes/no probability, `choice` with a
probability per option, `score` on an ordered scale), and the answer is numbers only, at
`<resource>/providers/microsoft/v1/systemone`. It therefore cannot write Controlled English and
cannot replace the compactor. It can judge compaction output, give a direct verdict, and
decide whether a requirement is hard. Three arms, all on data already on disk; no new blind
set is read and no prompt of P2g, P2g+ or the reader changes.

**X1, Decision-1 as fidelity judge.** Every judge item of the three judged runs (set2
`runs/20261015_reliability/judge/items`, 88; set3 `runs/20261015_set3/judge/items`, 60; Scout
`runs/20261015_hosts/scout/judge/items`, 20) is sent once: state = {source document, runtime
tool list, Controlled English pack}; five `noul` questions F1..F5 whose `instructions` and
`criteria` are the rubric text of the item (the same wording the Claude judge read), answered
without any Claude score in the request. A probability >= 0.5 is `yes`, otherwise `no`
(Decision-1 has no `unclear`; Claude's `unclear` is dropped from pairwise agreement). Metrics:
per-criterion yes-rate against the first judge's; pairwise agreement and Cohen's kappa with
the first judge on all items and with the second judge on the second-judge items; AUROC of
the probability against the first judge's yes/no.
- X1a: agreement with the first judge >= the second Claude judge's agreement with the first
  on the same items (set2 0.81, set3 0.85).
- X1b: on set3 the sign of the P2g -> P2g+ change in F1 and F4 yes-rates equals the Claude
  judge's (F1 down, F4 up). If X1a and X1b hold, Decision-1 is an admissible second judge and
  the B3 finding does not rest on one judge.

**X2, Decision-1 as direct verdict.** Arm `D-dec` on set2 (100) and set3 (100): state = the
exact user and system text of the saved D prompt (`prompts/D/<case>__s0.json`), so the two
direct-verdict arms read the same words; one `noul` question "a step the core deliverable
cannot do without cannot be done in this RUNTIME" with the D prompt's IMPOSSIBLE/ACHIEVABLE
definitions as `criteria`, and one `choice` question with options ACHIEVABLE, IMPOSSIBLE,
UNKNOWN. The verdict is the `choice`; the `noul` probability gives the operating curve.
Metrics as in R and C for arm D (decided accuracy, BLOCKED recall, false refutations, McNemar
against D gpt-5.4), plus AUROC and the false-refutation rate at the threshold that matches
gpt-5.4 D's recall. Documents over the context limit are truncated at the end and counted.
- X2a: decided accuracy within 5 points of gpt-5.4 D on the same set (set2 0.794, set3 0.771).
- X2b: at the threshold matching gpt-5.4 D's recall, false refutations not higher than D's.
Cost per call is recorded from `usage`.

**X3, Decision-1 as a hardness filter on refutations (exploratory).** For every refutation on
set3 by Rdet (witness requirement + evidence lines) and by P2g+ and P2g (the refuting `needs`
or guard, with the pack's Tool line), one `choice` question: is the named requirement a hard
requirement of the document's primary task (`hard` / `optional_or_alternative` /
`example_or_mention_only` / `cannot_tell`), state = document + requirement + evidence. A
refutation is kept only when `hard` wins. Measured: true refutations kept, false refutations
removed, for each arm, at the default choice and at a 0.7 threshold on `hard`.
- X3: removes at least half of the false refutations of each arm and keeps at least 90% of the
  true ones.
The reader's seven false refutations on set3 were found by reading set3, so a filter that
addresses them is tested on the set that produced them: X3 is optimistic by construction and
is reported as exploratory; a confirmatory number needs set4. X1 and X2 are not optimistic in
this sense (Decision-1 has not seen any of the documents and nothing is tuned on them).

**Implementation.** `scripts/decision1.py` with subcommands `judge`, `verdict`, `filter`,
`score`; one request per item, 40 requests/minute; every request and reply saved under
`runs/20261015_decision1/` with sha256s and `usage`; a reusable client
`skillc.frontend.providers.decision(state, questions, model)` with a unit test on a stub.
Thresholds (0.5, 0.7) are fixed here.

**Results pointer (Addendum D).** Ran 2026-10-15: 489 Decision-1 calls, 1,770,141 input tokens, no
errors, no truncation. All requests, replies, sha256s and `metrics.json` are in
`runs/20261015_decision1/`, and the write-up is `docs/DECISION_MODEL.md`. Criteria met:
X2a on set2, and X3 on P2g+ (exploratory). Criteria not met: X1a (set2, set3), X1b, X2a on
set3, X2b (set2, set3), and X3 on Rdet and P2g.

## Addendum E (2026-10-16, before set4 is drawn): closing the open items

Written before set4 exists. Sets 1, 2 and 3 are consumed and are now development sets: every
fix below may be developed and tuned on them. Set4 is read once, after the implementation
hashes are frozen in `runs/20261016_set4/frozen.json`.

### Open items and fixes

| id | open item (REVIEW_RESPONSE.md) | fix |
|---|---|---|
| E-a | the requirement reader reads optional, example and mention-only text as hard (7 of 82 on set3; 5 of the 7 are cloud accounts inferred from a prose mention) | **Rdet2.** A requirement inferred only from a prose mention (a library match outside a fenced command, with no credential variable, import, frontmatter entry or install route for it) is core only when its sentence carries a requirement cue (`must`, `required`, `requires`, `need(s)`, `only`, `cannot ... without`). Accounts are core only with operational evidence: a non-optional command of that service's CLI, its credential variable, or its SDK import. Everything else is unchanged. |
| E-b | recall: the compactor does not write `needs` for a refused host, a missing GPU, an absent account, a foreign agent tool | **Rllm**, a new arm: requirements extracted by a model, availability decided deterministically. gpt-5.4 reads the document only (never the runtime manifest) and returns JSON: primary task; requirements with `kind` (program, egress, credential, account, connector, tool, platform, hardware), `name`, `alternatives`, `hard`, `hard_basis` (`must`, `numbered_step`, `only_method`, `frontmatter`, `none`) and a verbatim `quote`. Deterministic guards: a requirement whose quote is not a substring of the document (after whitespace and markdown-emphasis normalisation) is dropped; `hard` is cleared when `hard_basis` is `none` or the quote lies in an optional passage (`nl._optional_lines`). Status comes from the manifest evaluator (`env/manifest.py`) as for Rdet; a requirement with alternatives is unavailable only if every alternative is. A hard, unavailable requirement refutes with reason `REQUIREMENT_UNAVAILABLE`; the witness is the quote plus the deciding manifest sentence. Because the extraction never sees a manifest, one extraction serves every runtime. |
| E-c | the universal `reply` tool lowers judged fidelity | **P2g++** = P2g+ plus (i) prompt rule 9 narrowed: `via reply` only for the Tool that adds a Goal atom the document says is written in the answer; analysis and planning are never Tools; (ii) a deterministic prune of dead `reply` Tools: a Tool bound `via reply` whose added atoms occur in no guard, no Goal and no message is removed. The prune cannot change a verdict (it removes only effects nothing reads); it removes invented steps. Fidelity rubric v2 adds one sentence to F1: "a Tool bound `via reply` that establishes the document's stated deliverable is not invented." Both rubric versions are reported. |
| E-d | multi-actor documents collapse into one role unless the prompt names the roles | Measured, not re-fixed: rule 14 (F-f) is in P2g+ but was never run on the Agent 365 intents without a role note. Run P2g++ on the ten `intent.md` (3 samples, named-vocabulary manifest) and re-score the separation-of-duty checks. These intents produced D7, so the number is a development number. Held-out: the set4 fidelity judge gets **F6** "every actor the document names as acting separately (approver, reviewer, second agent, human) has its own Role" (yes / no / not applicable). |
| E-e | environment contracts need the environment's state vocabulary; blind vocabulary gave 0 of 195 verdicts | **Alignment through bindings.** Before `apply_contracts`, for each pack Tool bound to an environment tool whose contract adds exactly one atom, and which is the only pack Tool adding its atom `p`, rename `p` to the contract's atom everywhere in the pack. Pack `init_true` names outside the vocabulary are dropped (the environment's initial state replaces them under contracts already). A name still outside the vocabulary after renaming leaves the pack unaligned, as now. Measured by re-scoring the 30 blind-vocabulary packs on disk (`runs/20261015_hosts/a365_blind`, no new model calls; these packs were never read for this design) and the 30 named-vocabulary packs (must stay at 189/195). |
| E-f | vendored copies of skillc in `examples/hosted-agent-finance*/src/` are behind | Re-sync from `src/skillc`; the examples' tests must pass. |
| E-g | every held-out set is consumed | **set4**: `select_cases.py --seed 20261006 --out benchmark/claude_env/set4 --exclude` the three earlier `cases.json`; 70 SKILL.md + 30 agent.md; labelled blind by ten annotators (Claude sub-agents, ten documents each) with `set3/RUBRIC.md` unchanged against `claude-code-cloud`. Annotators see only the rubric, the manifest and their ten documents. Implementers of E-a..E-e do not open `set4/`. |

### Arms on set4

gpt-5.4 (2026-03-05). P2g+ (frozen, 3 samples); P2g++ (3); Rllm (3); Rdet (as frozen for set3);
Rdet2; D (direct verdict, 1). Unions per sample: U1 = P2g+ ∪ Rdet (yesterday's default);
U2 = P2g++ ∪ Rdet2 ∪ Rllm (proposed default). Decision-1 hardness filter (X3, instructions
unchanged from `scripts/decision1.py`) applied to every refutation of Rdet2, Rllm and P2g++:
this is the confirmatory X3 that Addendum D deferred to set4. Fidelity judge: 30 documents
(sha256("set4-judge:"+case) order) for P2g+ and P2g++, rubric v1 and v2, plus F6; a second
judge on 20%.

### Criteria (set4)

- G1: U2 recall of BLOCKED (pooled over samples) at least D's recall minus 10 points.
- G2: U2 false refutations of ACHIEVABLE documents (pooled) at most 10%.
- G3: U2 decided accuracy higher than U1's (exact McNemar on the same samples reported).
- G4: Rdet2 false refutations at most half of Rdet's, and Rdet2 recall not lower than Rdet's
  by more than one document.
- G5: Rllm quote-verbatim rate at least 0.95; all-three-samples-agree rate reported.
- G6: P2g++ fidelity F1 (rubric v1) higher than P2g+'s on the same 30 documents; F4 not lower.
- G7: X3 on set4: the filter removes at least half of the false refutations of each filtered
  arm and keeps at least 90% of the true ones.
- G8 (development, Agent 365): with alignment, blind-vocabulary packs decide at least half of
  the 195 checks with zero disagreements whose expectation is ACHIEVABLE; named-vocabulary
  packs stay at 189/195. P2g++ separation-of-duty checks reported (no criterion).

Each criterion is reported met or not met. If G2 fails, U2 is not adopted as the default and
U1 stays. Nothing is tuned on set4 after it is read.

**Amendment to Addendum E (2026-10-16, after the set4 labels, before any set4 model call).**
A development run on set3 made Microsoft Defender for AI raise a phishing alert on the Azure
resource (15:24 UTC): a public benchmark document carried a listed URL. From now on, every
model request body is scrubbed by `skillc.frontend.urlguard`. URLs, bare domain names and
e-mail addresses become numbered placeholders, a request with anything URL-like left is
refused, and replies are restored. All set4 arms (P2g+, P2g++, Rllm, D) and Decision-1 run
scrubbed. Rdet and Rdet2 read the original text, since they make no model call. The scrubbed
prompt is a deterministic function of the saved prompt. Effect on comparability: the frozen
P2g+ and D numbers of sets 2 and 3 were measured unscrubbed, so set4 compares arms only with
each other, all scrubbed. A model that sees `[host-3]` cannot use what it knows about that
host. That may lower D's and Rllm's recall on egress requirements, and it is reported as a
limitation.
