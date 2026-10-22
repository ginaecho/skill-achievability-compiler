# Execution Atlas benchmarks

The benchmarks behind the Execution Atlas catalog. They are not part of the demo: the app does
not read these files. Run the scripts from the repository root; results are written next to them.
Topic and real-artifact data come from a `gc/data_train_test` worktree.

| file | what it is |
|---|---|
| `benchmark_catalog.py` | every topic form through compile, environment binding and check |
| `benchmark_real_artifacts.py` | every real public `SKILL.md`, agent and prompt in two environments |
| `refutation_metrics.py`, `refutation_audit.py` | confusion matrix with Wilson intervals; audit of `MISSING_CAPABILITY` refutations |
| `real-refutation-labels.json` | hand labels for the audit (they describe the benchmark; they never tune the frontend) |
| `benchmark-results*.json`, `real-benchmark-results*.{json,md}` | the recorded results |

`--llm` runs call a model. They need `SKILLC_ALLOW_MODEL_CALLS=1`, set on purpose for a run you agreed to,
and every request goes through the URL guard. Without `--llm` the runs are offline.

## Catalog benchmark

Run every topic form through the same deterministic compile, environment
binding, and check sequence used by the app:

```powershell
.\.venv\Scripts\python.exe demo\skillc-architecture-app\benchmark\benchmark_catalog.py `
  --catalog-root PATH_TO_DATA_TRAIN_TEST_WORKTREE
```

The command updates `benchmark-results.json` with per-case requirements,
grants, unavailable operations, verdicts, and comparison categories.
`expected_incompleteness` identifies the corpus's deliberate false-admission
examples; `frontend_abstention` identifies prose that deterministic compaction
cannot yet formalize; `mismatch` is an unexpected labeled disagreement. The
report also records any topic whose verdict differs across its three forms.
Compilation uses the environment's tools as the capability context, and
binding then removes any capability the environment does not grant and applies
the environment's contracts. Add `--llm DEPLOYMENT` (with
`AZURE_OPENAI_ENDPOINT` and `AZURE_SUBSCRIPTION_ID` set) to compact with Azure
OpenAI instead; results go to `benchmark-results-llm.json`, including each
compacted and bound pack. Only the LLM calls run in parallel: z3 is not
thread-safe, so every check runs on one thread. `--reuse FILE` re-checks the
packs stored in an earlier LLM results file without calling the LLM again, so a
binding or checker change can be measured on identical compactions.

## Real artifact benchmark

`benchmark_real_artifacts.py` checks every real, externally published artifact
on `gc/data_train_test` (588 `SKILL.md` files from 5 pinned public pools) plus
168 agents and 143 prompts pinned from `github/awesome-copilot@e13e02be`
(MIT) by `scripts\fetch_copilot_sources.py`. Authored fixtures are excluded,
duplicates are removed by SHA-256, and any file whose bytes differ from its
manifest is excluded and listed under `integrity_exclusions`.

```powershell
.\.venv\Scripts\python.exe scripts\fetch_copilot_sources.py `
  PATH_TO_DATA_TRAIN_TEST_WORKTREE\benchmark\copilot_sources
.\.venv\Scripts\python.exe demo\skillc-architecture-app\benchmark\benchmark_real_artifacts.py `
  --data-root PATH_TO_DATA_TRAIN_TEST_WORKTREE
```

Each artifact is checked in two environments: its home runtime
(`claude-code` for skills, the documented `vscode-copilot` profile for agents
and prompts) and the cached observed environment. The report is written to
`real-benchmark-results.json` and `real-benchmark-results.md`, with a balanced
headline subset of equal size per kind.

Every `MISSING_CAPABILITY` refutation is audited against
`real-refutation-labels.json`, hand labels that classify each frontier name as
a real absent tool (MCP server, extension, or another runtime's tool), a
deterministic- or LLM-frontend misextraction, or a `runtime_name_variant` (an
undocumented spelling of a VS Code built-in, counted as non-confirming). The
labels describe the benchmark; they are not used to tune the frontend.

`--llm DEPLOYMENT` compacts each artifact once with Azure OpenAI and checks
that pack in both environments; `--balanced-only` limits the run to the
balanced subset, `--per-kind N` runs a pilot, and `--reuse FILE` re-checks the
stored packs without calling the LLM again. Topic benchmark results include a
refutation confusion matrix (positive = `IMPOSSIBLE`) with Wilson 95%
intervals per form.

When multiple input types are selected, their tool metadata is combined and their
bodies become labeled sections in one temporary `COMPOSITE.md`. SkillC compiles
and checks that composite once; it does not aggregate separate verdicts.
