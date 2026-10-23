# Execution Atlas

**Shows:** one skill, agent file or prompt moving through the real skillc compiler, stage by stage,
and why the same intent is `ACHIEVABLE` in one environment and `IMPOSSIBLE` in another.
**Audience:** engineers who want to see inside the checker. **Time:** 5 minutes.

## Run it

```bash
pip install -e ".[dev]"
python demo/skillc-architecture-app/app.py      # opens 127.0.0.1:8765
```

Offline by default (deterministic compaction). The catalog of tested intents is read through git
from the `gc/data_train_test` branch, so fetch it once (`git fetch origin gc/data_train_test`);
without it you can still paste your own text.

## Present it

1. Under **Tested intent library**, pick a topic. Its `SKILL.md`, `agent.md` and prompt load together;
   tick which ones to include.
2. Set **Environment snapshot** to **Selected case** and press **Run**. Walk the **Intermediate
   evidence graph** left to right: received source, compaction, environment, binding, schema,
   capability, reachability, verdict. Click a node to show its input, its output and the Python
   functions that produced it.
3. Switch **Environment snapshot** to **Current environment · automatically observed** (this folder
   as GitHub Copilot CLI sees it; **Refresh now** reads it again) and run the same intent. Point at
   the binding node: the tools the intent needs that this machine lacks are why the verdict changes.
4. Paste a free-form prompt. Show `UNKNOWN [INCOMPLETE_COMPACTION]`: skillc abstains instead of
   guessing, and an abstention never permits the run.

## Reference


A local browser app that illustrates SkillC's real execution structure. It accepts
`SKILL.md`, `agent.md`, or prompt text and streams:

- a selectable library of tested intents on `gc/data_train_test`: topics, each
  written natively as a `SKILL.md`, an `agent.md`, and a prompt, plus real
  public artifacts;
- checkbox selection for combining `SKILL.md`, `agent.md`, and prompt content
  into one composite instruction and one SkillC decision;
- intent-required capabilities and independently selected environment grants;
- the requirement-to-grant binding, including every required but unavailable
  operation;
- a clickable evidence-graph node for every execution stage, including received
  source, compaction provenance, environment snapshot input, bound pack,
  schema result, capability result, projections/conformance, reachability, and
  final verdict;
- each stage's first-entered SkillC Python functions with source files and lines;
- the actual `skillc compile` output (the formal pack);
- the actual `skillc check --json` terminal output and exit code.

The frontend is presentation-only. Verdicts and traces come from the repository's
installed Python code; no result is simulated.

The **Intermediate evidence graph** replaces the former execution-card and
standalone Python-trace panels. It shows the causal dataflow while the terminal
retains the raw command log. The received source and observed environment are separate
inputs that converge at requirement binding; the bound pack then flows through
schema validation, capability existence, interaction checking, reachability,
and the verdict. Select a graph node to inspect:

- the exact upstream artifact supplied to that stage;
- the stage's JSON output;
- the Python files, functions, and source lines that examined it;
- the rule explaining how that result controls later stages or the verdict.

An intent's `Tools`, `Required tools`, `allowed-tools`, or agent `tools`
declaration describes **required capabilities**. It does not prove that the
coding environment supplies them. The app loads the cached
`.skillc/env/latest.json` snapshot produced by the existing `skillc.env`
read-only probe, binds the requirement pack to its observed grants, and checks
the bound pack. Thus the same complete intent can be
`IMPOSSIBLE [MISSING_CAPABILITY]` in one environment and `ACHIEVABLE` in another.

The first app launch probes automatically. The snapshot is retained across app
restarts, refreshed hourly by default, and refreshed on demand by **Refresh
now**. Change the schedule with `--environment-refresh-seconds`; use `0` to
disable scheduled refresh. The recorded environment paired with a catalog case
remains selectable for reproducing that benchmark without editing a tool list.

An unstructured prompt for which deterministic compaction extracts neither the
task goal nor required operations returns `UNKNOWN [INCOMPLETE_COMPACTION]`.
Explicit web-search and flight-booking requests are preserved as required
operations, so a missing booking grant is instead refuted as
`IMPOSSIBLE [MISSING_CAPABILITY]`.
`UNKNOWN` blocks execution but is not relabeled `IMPOSSIBLE`: only a sound
refutation may use that label. Semantic compaction or a reviewed contract can
first establish the requirements; if the observed environment then lacks a
required operation, the checker returns `IMPOSSIBLE [MISSING_CAPABILITY]`.

The catalog has two suites. **Topics** (`corpus/intents/<topic>/`) are 132
intents: the 24 reference corpus cases, 8 compaction tasks, and 100 newer
natural topics across 36 domains (44 achievable, 48 impossible, 8 unknown).
Each newer topic carries a formal `reference_pack` in `topic.json`, and
`corpus/validate_topics.py` checks mechanically that the checker's verdict on
it equals the stated label. Each topic is written three times, natively and differently — a reusable `SKILL.md`
procedure, an `agent.md` persona, and a user prompt — plus `environment.json`,
a SkillC runtime manifest describing the tools the environment provides and
what they do. Selecting any form loads all three. The intent files state
requirements only: what the environment provides, how its tools behave, and
anything that would reveal the verdict appear only in `environment.json`, and
`tests/test_topic_intents.py` on the data branch enforces this. **Real public
artifacts** are a balanced set of 143 real `SKILL.md`, agent, and prompt files;
each loads only its own native form, and nothing is generated for the others.

Names never show expected verdicts. With **Selected case** as the environment,
a topic runs against its `environment.json`; a real artifact runs against its
home runtime profile.

A topic environment also publishes formal **tool contracts** (`contracts`:
pre / add / del / nondet per tool), a **state vocabulary** (`states`) and its
initial state (`init_true`), generated by `corpus/build_topic_contracts.py` on
the data branch. Binding (`skillc.frontend.contracts.bind_environment`) first
removes tools the environment does not grant, then replaces the intent's
assumed tool behaviour with the environment's contracts — but only when the
intent's goal is written in the environment's state vocabulary; otherwise the
contracts are left out and the unaligned names are reported, so contracts can
never cause a false refutation. LLM compaction receives the tool and state
names (never the contracts) via `--vocabulary`.

The same vocabulary guards the verdict. A refutation must rest on names the
inputs contain: a `GOAL_UNSAT` or `BLOCKED_GUARD` condition must be in the
environment's state vocabulary (or, if the environment publishes none, in the
intent text), and a `MISSING_CAPABILITY` tool must be named in the intent text
or extracted from it. A refutation whose deciding names were invented by a
compactor (for example `card_selected`) says something about the compaction,
not the intent, so `skillc check --vocabulary environment.json --source
intent.md` reports it as `UNKNOWN [UNALIGNED_CONDITION]` or
`UNKNOWN [UNGROUNDED_TOOL]` instead of `IMPOSSIBLE`. A reviewed `--contract`
also counts as an input.

### Azure Foundry semantic compaction

Select **Azure Foundry LLM** to use SkillC's existing opt-in Azure OpenAI
semantic frontend. Configure defaults when starting the app:

```powershell
.\.venv\Scripts\python.exe demo\skillc-architecture-app\app.py `
  --foundry-project-endpoint "https://RESOURCE.services.ai.azure.com/api/projects/PROJECT" `
  --azure-openai-endpoint "https://RESOURCE.openai.azure.com/openai/v1" `
  --model "DEPLOYMENT_NAME" `
  --azure-subscription "SUBSCRIPTION_ID"
```

Authentication uses `AZURE_OPENAI_API_KEY` from the server environment when set;
otherwise it requests an Azure CLI token for `--azure-subscription` (the
subscription that owns the Foundry resource), so the global `az` default
account need not match. `--model` is the deployment name exactly as listed by
`az cognitiveservices account deployment list`. Keys are never accepted by or
returned to the browser. The LLM is outside the trusted decision path: its pack is
schema-validated and the normal checker emits the verdict.

Above the evidence graph, the verdict panel always shows the checker's verdict,
reason, detail, and frontier. With the LLM on, a second call
(`skillc.frontend.llm.explain_verdict`) adds a plain-language explanation of
that verdict, labelled untrusted: it explains but never decides. The panel and
the terminal also report LLM token usage — calls, input (and cached) tokens,
output tokens, and totals — separately for compaction and explanation,
collected with `skillc.frontend.providers.metered()`.

## Run

From the repository root:

```powershell
.\.venv\Scripts\python.exe demo\skillc-architecture-app\app.py
```

The app opens at <http://127.0.0.1:8765>. Use `--no-browser` to prevent automatic
browser launch, or `--port` to select another port.

Use `--catalog-root PATH` to preview uncommitted benchmark fixtures from a
`gc/data_train_test` worktree instead of the remote-tracking branch.

The server binds to localhost by default, limits input to 100 KB, writes each input
to a temporary directory, and removes it when the run completes.


The catalog and real-artifact benchmarks are in [`benchmark/`](benchmark/README.md).
