# Can this workflow finish here? SkillC versus plain and guided LLM agents

**Finding:** on seven bounded local workflows, SkillC consistently identified the
blocked tasks before task execution, without spending model tokens. The LLMs
also avoided false definitive claims, but sometimes performed task work
or stopped with `UNKNOWN`. This is evidence for predictable, low-cost preflight
on an authored workflow graph, not universal superiority over an LLM.

## 1. The three questions

| Question | What this experiment establishes |
|---|---|
| Can SkillC discover prerequisites without a person entering environment facts? | Yes for the local programs and Python modules used here: the runner probes the machine automatically. This does not establish complete discovery of an active agent session, cloud permissions or live MCP tools. |
| Is it better than a plain LLM? | It gave a definite correct verdict in every trial and stopped earlier on blocked tasks, using no model tokens. The plain LLM made no false definite claim either; its one missing answer was an abstention. |
| Does environment-first skill/agent guidance close the gap? | It improved early stopping from 7/12 to 9/12 blocked trials, but did not make it consistent. The guided LLM also abstained twice and spent more tokens. This small sample does not establish that guidance generally reduces accuracy. |

## 2. Setup: same task and operation graph, different decision method

Measured on **22 October 2026**, using the **`gpt-5.4` deployment through Azure
OpenAI** for both LLM methods. There were **seven workflows**, **three
repetitions per method**, and **three methods**: **63 trials**, not 63 independent
cases.

| Method | Inputs and behavior |
|---|---|
| Plain LLM | Receives the task, fixed operation contracts and access to a read-only environment discovery tool. Chooses operations or a final verdict. |
| Guided LLM | Receives the same inputs, plus skill/agent-style instructions to inspect tools, permissions and every workflow branch before working. |
| SkillC | Receives the same authored workflow graph and automatically probed prerequisites. Uses deterministic static validation, then executes a feasible plan or stops. |

All methods are restricted to the same fixed operations. There is no arbitrary
shell execution, package installation or alternative implementation. This matters:
"Word using pandoc" is blocked if pandoc is absent, even if another unoffered
tool could create a Word file.

Ground truth comes from a **separate runtime verification runner** that attempts
each fixed workflow, including those SkillC refuses. It verifies actual Git
history, reports, archives and graph outputs. Neither SkillC's verdict nor an
LLM's claim is accepted as proof of task completion.

## 3. Results

| Method | Correct definite verdicts | Abstentions (`UNKNOWN`) | Early stops on blocked tasks | Completed feasible tasks | Total model tokens |
|---|---:|---:|---:|---:|---:|
| Plain LLM | 20/21 (95.2%) | 1 | 7/12 (58.3%) | 9/9 | 33,047 |
| Guided LLM | 19/21 (90.5%) | 2 | 9/12 (75.0%) | 8/9 | 44,724 |
| SkillC | 21/21 (100%) | 0 | 12/12 (100%) | 9/9 | 0 |

**None of the three methods made a false definite verdict:** zero false
`IMPOSSIBLE` answers and zero false `ACHIEVABLE` answers. The lower LLM
correct-verdict counts reflect abstentions, not incorrect definite claims.
The guided LLM left one feasible ZIP task unfinished after successfully reading
the history; it returned `UNKNOWN` instead of continuing.

| Metric | Exact meaning |
|---|---|
| Correct definite verdicts | `ACHIEVABLE` or `IMPOSSIBLE` agrees with independent runtime verification. `UNKNOWN` does not count as correct, but is reported separately from a false claim. |
| Early stop | Correctly declares the whole task impossible before executing any task operation. Read-only discovery is allowed first. |
| Completed feasible tasks | All requested artifacts passed runtime verification, not merely a success statement from the model. |
| Total model tokens | Provider-reported input plus output across all 21 trials of that method, not tokens per workflow. |

There are **nine feasible trials** (three feasible workflows repeated three times)
and **12 blocked trials** (four blocked workflows repeated three times) per
method. All three methods had zero inference/execution errors in the completed
comparison.

For audit: plain used 30,194 input + 2,853 output tokens in 65 model calls; guided
used 40,984 + 3,740 in 70 calls. Median orchestration wall times were about 15.18 s,
17.30 s and 32.26 ms respectively. These include authentication, network and local
scheduling, are not isolated inference timings, and exclude separately recorded
shared discovery time.

## 4. The seven workflows and observed outcomes

| Workflow | What was requested | Runtime verification result |
|---|---|---|
| Release report | Read the latest five commits and write a Markdown report | Feasible; report content matched the Git history. |
| Release archive | Create that report and package it as a ZIP | Feasible; archive content matched the report. |
| Word handoff | Convert the report to Word using pandoc | Blocked; pandoc was not installed. |
| Excel history | Export commit history using openpyxl | Blocked; openpyxl was not installed. |
| Building inventory | Parse the repository's campus graph and count its triples | Feasible; a real parser produced a verified inventory of a synthetic building graph. |
| Combined handoff | Produce a release ZIP, Word document and graph inventory | Partially feasible; ZIP and inventory worked, Word was blocked. |
| Restricted output | Copy the report outside the permitted output directory | Blocked by the explicit benchmark sandbox policy, not an observed OS or cloud permission. |

The branching case illustrates the distinction between **the full request** and
**its feasible parts**:

```text
Read Git history -> Markdown report -> ZIP archive       feasible
                                  \-> Word via pandoc  blocked: pandoc absent
Parse building graph -> inventory                      feasible

Full request: blocked, because it requires all three deliverables.
Useful partial plan: report + ZIP + graph inventory.
```

SkillC saves the partial plan, per-deliverable statuses, reasons and checker
certificates. In this experiment the early-stop policy does not execute those
feasible branches. The separate runtime verification runner still attempts them.
Per-node prediction accuracy for the LLM baselines was not measured.

## 5. What not to infer

The operation graph and contracts are **authored**, not inferred from arbitrary
prose. SkillC's zero tokens apply to that static validation path; optional LLM
compaction has a separate cost. Task feasibility and artifact validity are
measured, not release-note prose quality.

The cases are newly authored practical workflows over repository artifacts, not
sampled production incidents. The building graph is synthetic. The
restricted-output case measures an explicit sandbox boundary, not discovery of
real Windows ACLs or Azure roles. MCP configuration was read without live tool
enumeration or authentication checks. The introductory demo's Claude Code
profile is not a live inventory of the active Copilot session, and ask-first
tools remain conditional on approval.

No email, deployment, cloud write or outside-directory write was performed.
Only guarded model inference was remote. This is one machine, one deployment
and seven workflows; repetitions do not establish broad statistical superiority.

## 6. See or reproduce it

Run the [introductory demo](../demo/skillc-here/README.md):

```powershell
python demo\skillc-here\app.py
```

Open **3 · Why skillc**. The dated published comparison is available without
local run files; the separate local-measurements panel reads your newest run
and labels incomplete or offline-only runs.

The [benchmark runner](../scripts/benchmark_here.py) writes an offline comparison
of SkillC and independent runtime verification by default:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_here.py --repeats 1
```

For fresh LLM measurements, follow the explicit provider opt-in instructions in
the [demo README](../demo/skillc-here/README.md#fresh-measurements-separate-from-the-replays).
No additional model run was used to prepare this explanation.

The underlying local evidence is
`runs\20261022_183400_here_benchmark\`: `results.json`, `REPORT.md`, model
transcripts, provider usage, preflight certificates, output artifacts and an
audit of 90 successful artifact checks. Raw runs and prompt logs stay local;
this document publishes only the curated explanation and aggregate findings.
