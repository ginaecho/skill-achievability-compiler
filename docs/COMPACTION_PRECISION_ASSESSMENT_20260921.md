# Compaction precision: deterministic versus LLM

Date: 2026-09-21. Positive class throughout this report: **IMPOSSIBLE**.

## Main conclusion

LLM compaction recovered substantially more semantic structure than the
deterministic fallback. Clarifying goal-checkpoint semantics eliminated three
false rejections in a fresh pass over the same 32 scenarios. Separately,
conservative goal-only checking prevented unsupported refutations by
abstaining, without needing another model call.

The LLM must not decide what capabilities exist or silently redefine the task.
The recommended architecture separates three responsibilities:

1. Supply an explicit task/environment contract.
2. Use deterministic or LLM compaction to propose a protocol.
3. Reject the broader goal only with a protocol-independent certificate;
   otherwise abstain when the extracted protocol is defective.

This is not a change to the paper's objective or a claim that a different
protocol satisfies the original session-typing judgment. The default
protocol judgment remains available and unchanged in scope.

## Dataset and what "real" means here

Eight unchanged, pinned public skill documents cover six categories:

| Category | Upstream skill |
|---|---|
| Data extraction | `google/langextract`: LangExtract usage |
| Databases | `microsoft/skills`: PostgreSQL ARM .NET |
| Databases | `microsoft/skills`: Cosmos DB ARM .NET |
| Containers/infrastructure | `microsoft/aspire-skills`: orchestration |
| Containers/infrastructure | `microsoft/aspire-skills`: deployment |
| Cloud observability | `microsoft/skills`: Azure Monitor OpenTelemetry Java |
| ML/datasets | `huggingface/skills`: Dataset Viewer |
| Collaboration/source control | `cli/cli`: code review |

Primary-source URLs, exact commits and license evidence are in
[`REAL_CASE_EXPANSION_SOURCES.md`](REAL_CASE_EXPANSION_SOURCES.md) and
[`sources.json`](../benchmark/compaction_sources/sources.json).
The resolved Aspire files, not the plugin symlink text, were used.
Each source retains its license from the same commit.
The Hugging Face trainer candidate was excluded because its local license
reference was unresolved.

Each source has four separately authored invocation environments:
complete, missing essential operation(s), missing optional operation, and a
permanently blocked required guard. This gives **32 scenarios: 16 achievable
and 16 impossible** in their fixed reference models.

These are **real documents with authored task contracts and seeded
restrictions**, not 32 observed production failures. No cloud resources were
provisioned, no source commands executed, no dataset rows fetched, and no
actual PR reviewed. The new comparison measures compaction/checking, not
with-versus-without-SkillC backend execution.

Important task distinctions are explicit: PostgreSQL/Cosmos goals require
resources to exist, not just code generation; Aspire deployment requires
deployment rather than publishing artifacts; local Aspire orchestration
requires no cloud credential; public dataset reading requires no upload
token; a static code review does not require running Go tests. LangExtract
and Aspire deployment retain alternative providers/targets. Aspire
orchestration includes cleanup in its actual goal.

The effects themselves are abstraction assumptions. For example, a
`deliver_review` effect does not establish that a review is correct, and an
`extract_*` effect does not prove that an LLM's entities are accurate.

## Fairness and independent labels

Both front ends receive the **same full source, invocation and explicit
contract information**. The deterministic profile additionally exposes the
same capability identifiers in its native profile interface. The harness
does not assume the stock CLI's deterministic `--profile` automatically
configures the LLM provider.

The benchmark therefore tests **contract-informed compaction**, not
unassisted understanding of arbitrary natural language. "Unbound" below
means the extracted fields are not overwritten afterward; it does **not**
mean the model was denied the contract information.

Before any model call, the harness freezes source hashes, invocation text,
contracts, labels and implementation snapshots. An independent interpreter
in `scripts/benchmark_semantics.py`, which does not import the checker,
establishes reference labels through concrete abstract-model witnesses,
missing-establisher proofs, or exhaustive Boolean search. The 16 positive
reference cases have 42 recorded action transitions in total.

The checker and oracle both use Z3, so they are implementation-independent
but not solver-independent. Labels are about any legal plan in the fixed
contract; they are not supplied by the evaluated LLM or derived from its
generated pack.

There are only eight source families, with correlated variants. Each prompt
version receives one compaction per scenario, not repeated sampling.
Results do not estimate production prevalence, model variance, or
generalization to unseen skills. All scenarios are finite Boolean models;
this expansion is not a new evaluation of numeric abstraction, MPST
multi-role coverage, or real payload correctness.

## Baseline: six paired configurations

Baseline evidence:
[`20260921_113746Z_compaction_comparison`](../runs/20260921_113746Z_compaction_comparison).
Model: `gpt-5.4-2026-03-05`.

| Configuration | TP | FP | FN | TN | Precision | Recall, all impossible | FPR, all achievable | Unknown | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Deterministic, unbound protocol | 6 | 6 | 10 | 10 | 50.00% | 37.50% | 37.50% | 0 | 100% |
| LLM, unbound protocol | 16 | 3 | 0 | 13 | 84.21% | 100% | 18.75% | 0 | 100% |
| Deterministic + contract, protocol scope | 16 | 16 | 0 | 0 | 50.00% | 100% | 100% | 0 | 100% |
| LLM + contract, protocol scope | 16 | 3 | 0 | 13 | 84.21% | 100% | 18.75% | 0 | 100% |
| Deterministic + contract, goal-only | 16 | 0 | 0 | 0 | 100% | 100% | 0% | 16 | 50.00% |
| LLM + contract, goal-only | 16 | 0 | 0 | 13 | 100% | 100% | 0% | 3 | 90.63% |

Precision = TP/(TP+FP). Recall in this table is TP/16, including every
labelled impossible case in the denominator even if the checker abstains.
FPR here is FP/16, across all labelled achievable cases. Coverage counts
non-abstaining decisions. Unknown is not counted as either admission or
rejection; FN counts definite false admissions, not abstentions.

`metrics.json` also provides conventional decided-case FPR = FP/(FP+TN).
It is **undefined**, not zero, for deterministic + contract + goal-only:
that variant admitted no achievable cases. Its zero overall false-rejection
rate must be read together with its 50% coverage.

### Why the deterministic numbers are weak

All 32 deterministic compactions fell back to `tool_usage_only`; **none
captured the actual requested goal**. Some turned prose identifiers such as
`extraction_class` or `max_workers` into missing tools; others invoked a
generic `bash` capability not present in the adapter contract. Twenty
fallback packs had trivial goals.

The unbound row consequently measures end-to-end task misclassification,
not a soundness failure of the checker on its own different goal. Binding
the correct goal alone does not repair a missing/wrong protocol: the
contract-bound protocol variant rejected all 32 cases. Goal-only checking
prevents those bad protocols from being promoted into unsupported
impossibility claims, but abstains on all 16 achievable cases.

### Why the baseline LLM still falsely rejected three tasks

The LLM preserved all 32 goals exactly and neither added nor omitted
capability identifiers. Its three false rejections were:

| Scenario | Extraction defect |
|---|---|
| LangExtract, missing optional visualization | Goal checkpoint placed before extraction/save |
| Aspire orchestration, missing optional diagnostics | Goal checkpoint placed before start/wait/describe/stop |
| GitHub CLI review, missing optional Go tests | Goal checkpoint placed before reading and delivering review |

A protocol `{"goal": ...}` is an assertion **at that point**, not a
declaration of future intent. These three packs asserted completion at
the beginning. The checker correctly rejected their protocols; that did
not establish that the requested tasks were impossible. Binding keeps
checkpoint positions intact rather than silently "repairing" the plan.
Goal-only mode turned these three outcomes into honest abstentions.

### Baseline category detail

Cells show `TP / FP / FN / TN / unknown`.

| Category | N | Deterministic unbound | LLM unbound | Deterministic contract + goal | LLM contract + goal |
|---|---:|---|---|---|---|
| Data extraction | 4 | 2 / 2 / 0 / 0 / 0 | 2 / 1 / 0 / 1 / 0 | 2 / 0 / 0 / 0 / 2 | 2 / 0 / 0 / 1 / 1 |
| Databases | 8 | 2 / 2 / 2 / 2 / 0 | 4 / 0 / 0 / 4 / 0 | 4 / 0 / 0 / 0 / 4 | 4 / 0 / 0 / 4 / 0 |
| Containers/infrastructure | 8 | 0 / 0 / 4 / 4 / 0 | 4 / 1 / 0 / 3 / 0 | 4 / 0 / 0 / 0 / 4 | 4 / 0 / 0 / 3 / 1 |
| Observability | 4 | 0 / 0 / 2 / 2 / 0 | 2 / 0 / 0 / 2 / 0 | 2 / 0 / 0 / 0 / 2 | 2 / 0 / 0 / 2 / 0 |
| ML/datasets | 4 | 2 / 2 / 0 / 0 / 0 | 2 / 0 / 0 / 2 / 0 | 2 / 0 / 0 / 0 / 2 | 2 / 0 / 0 / 2 / 0 |
| Collaboration/source control | 4 | 0 / 0 / 2 / 2 / 0 | 2 / 1 / 0 / 1 / 0 | 2 / 0 / 0 / 0 / 2 | 2 / 0 / 0 / 1 / 1 |

## Fresh follow-up with the clarified LLM prompt

Follow-up evidence:
[`20260921_114226Z_compaction_comparison`](../runs/20260921_114226Z_compaction_comparison).
All **32 input, contract and oracle hashes are identical** to the baseline.
Every scenario was recompiled with a fresh live call; the three problematic
cases were not the only cases rerun. No generated pack was manually repaired.

| Configuration | TP | FP | FN | TN | Precision | Recall | FPR | Unknown | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Revised LLM, unbound protocol | 16 | 0 | 0 | 16 | 100% | 100% | 0% | 0 | 100% |
| Revised LLM + contract, protocol scope | 16 | 0 | 0 | 16 | 100% | 100% | 0% | 0 | 100% |
| Revised LLM + contract, goal-only | 16 | 0 | 0 | 16 | 100% | 100% | 0% | 0 | 100% |

All deterministic rows were unchanged. The revised LLM preserved the exact
goal and capability identifier set in all 32 cases. Per-category results
are in the follow-up `metrics.json`: all six categories had zero false
rejections and zero missed impossible cases in this pass.

This is **not proof of 100% production precision**. The prompt was improved
using these observed errors; this is a development-set follow-up with one
sample per scenario. It suggests that explaining formal marker semantics
is useful, but does not isolate prompt effects from model sampling variance.
Keep contract binding and goal-only safeguards even when this sample no
longer needs their abstention path.

## Implemented improvements

**Explicit refutation scope.** Verdict JSON separates `declared_protocol`
from `capability_context`. The opt-in `--goal-only` policy refuses to
equate a protocol error with impossibility across alternative plans.
Default protocol semantics and the paper's typing rules are not weakened.

**Authoritative contract binding.** `--contract` fixes the goal, grants,
guards/effects and initial conditions, retaining all permitted alternatives.
It is an additional trust input, not extraction magic or MCP discovery.
This guards against invented grants and silently weakened goals, provided
the contract itself accurately describes the runtime.

**Guard-aware conservative certificates.** Starting from initial true
predicates, the checker adds effects of potentially enabled capabilities
to a fixed point. Deletes are ignored, possible Boolean atoms are left
free, and numeric comparisons are abstracted as free Booleans. This
over-approximates possible producers; only unsatisfiability permits
refutation. A missing prerequisite with no producer can now be proved
unreachable even when the final capability exists. The algorithm is not
a complete planner, and the executable extension is not mechanized in Coq.

**Incomplete-compaction abstention.** Deterministic fallback provenance is
explicit. The goal-only CLI returns `UNKNOWN/INCOMPLETE_COMPACTION` when
only tool usage, rather than a semantic goal, was extracted without a contract.
This prevents a trivial `True` goal being mistaken for task understanding.

**Confirmed SMT-name collision fixed.** A real regression reproduced a false
refutation when a user predicate named `__cmp_0` collided with an internal
arithmetic placeholder. Predicate and arithmetic namespaces are now separate.
This is a genuine implementation bug, unlike rejecting a badly extracted
protocol. A regression went red before the fix and green afterward.
All 192 baseline verdicts were replayed after the fix and were unchanged.

**Goal-marker prompt clarified.** The LLM schema/prompt now says that the
top-level goal is checked at termination and that protocol goal markers are
checkpoints, not declarations. It tells the compactor to omit such markers
unless a checkpoint is required by the source. This addresses the observed
three extraction defects without moving checkpoints in the trusted checker.

## Replay of the previous five-source benchmark

The ten earlier full/restricted packs were left unchanged and replayed with
the new policy; no new model calls were needed.

| Policy | TP | FP | TN | Precision | Recall | FPR | Unknown | Coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Default protocol judgment against any-plan goal labels | 4 | 5 | 1 | 44.44% | 100% | 83.33% | 0 | 100% |
| Goal-only policy against the same labels | 4 | 0 | 1 | 100% | 100% | 0% | 5 | 50% |

The five false rejections became abstentions, **not successful executions**.
Evidence: `prior_pack_replay.json` and `replay_prior.py` in the baseline run.
The earlier with/without-SkillC simulation and its token accounting remain
separate; see [`BENCHMARK_CORRECTION_20260921.md`](BENCHMARK_CORRECTION_20260921.md).

## Accounting, provenance and reproduction

| Live compaction pass | Calls | Input tokens | Output tokens | Total tokens | Cached input, included in input | Sum of request latency |
|---|---:|---:|---:|---:|---:|---:|
| Baseline prompt | 32 | 103,429 | 12,151 | 115,580 | 75,392 | 125.951 s |
| Clarified prompt | 32 | 105,701 | 10,560 | 116,261 | 73,216 | 115.403 s |
| Total | 64 | 209,130 | 22,711 | 231,841 | 148,608 | 241.354 s |

All 64 calls returned HTTP 200, `finish_reason=stop`, and model
`gpt-5.4-2026-03-05`. No schema retry was needed. Deterministic compaction and
the contract/scope ablations made **zero model calls**. Cached input is not
subtracted from the total-token column; this is not a dollar-cost estimate.
Summed API latency is not an end-to-end or controlled speed comparison.

Each run stores source/license snapshots, prepared invocations, contracts,
reference witnesses/proofs, raw API outputs, request hashes, token usage,
generated packs, six-way verdicts, category metrics and implementation
snapshots. `verification.json` reconciles API request hashes and usage,
replays all 192 verdicts per run against the final checker, and verifies
the 42 reference witness transitions per run. The baseline snapshot
predates the SMT namespace fix; its replay under the final implementation
produced identical verdicts.

Prepare and execute a new run:

```powershell
python scripts\benchmark_compaction.py --prepare
python scripts\benchmark_compaction.py --run-dir runs\<new-directory> --live
```

`--live` uses the existing Azure OpenAI configuration/identity; it never
performs the skills' underlying actions. Omit it for deterministic-only
execution. The run refuses changed implementation files or inputs on resume.
To verify either saved live run without another model call:

```powershell
python scripts\verify_compaction_benchmark.py runs\20260921_113746Z_compaction_comparison
python scripts\verify_compaction_benchmark.py runs\20260921_114226Z_compaction_comparison
```

## Deployment recommendation and remaining work

Use the LLM to propose semantic structure; keep schema validation, SMT and
protocol checking deterministic. Require a reviewed environment adapter
contract for rejection-sensitive use. Route `UNKNOWN` to review, revised
compaction, or another explicitly authorized policy; never silently treat it
as permission to execute.

The next evidence improvement should be **held-out real invocation tasks**,
multiple compaction samples, independently reviewed intent/effect annotations,
and actual sandboxed backend executions where authorized. Add numeric,
multi-role and unmodeled-failure cases rather than assuming these Boolean
results generalize. A local-to-MCP capability mapping needs explicit adapter
evidence; automatic MCP discovery/association is not implemented here.

The improved prompt was developed after inspecting this benchmark's errors.
Its follow-up is therefore a development-set result, not a held-out causal
estimate. No task, source, environment contract or reference label is changed
between prompt versions.
