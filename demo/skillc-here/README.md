# skillc here

**Shows:** skillc reading this folder by itself the way GitHub Copilot CLI sees it (tools, saved
approvals, MCP servers) and deciding what a skill can do here, next to Copilot CLI, VS Code Copilot,
Claude Code and claude.ai; and, for an uploaded graph, what a workflow can establish from it and what
is missing; and **why** skillc, next to an LLM alone and an LLM with a guiding skill. **Audience:**
first-time viewers. **Time:** 3 to 6 minutes.

## Run it

```bash
pip install -e ".[twin]"          # skillc, plus rdflib for the graph tab
python demo/skillc-here/app.py    # opens http://127.0.0.1:8770/
```

Offline by default: no model call, no network check, nothing is executed. The server binds to
127.0.0.1 and answers only requests addressed to `127.0.0.1` or `localhost`.

**With the LLM columns** (tab 1 then also asks a plain LLM and a guided LLM; each check calls a
model twice and costs tokens), opt in for this run only:

```powershell
$env:SKILLC_ALLOW_MODEL_CALLS = '1'
$env:AZURE_OPENAI_ENDPOINT = '<your Azure OpenAI endpoint>'
python demo/skillc-here/app.py --llm --llm-provider azure-openai --model <deployment>
```

Azure CLI sign-in or `AZURE_OPENAI_API_KEY` authenticates; `--llm-provider anthropic` uses
`ANTHROPIC_API_KEY`. Without the opt-in the columns stay off and say why.

## Present it

1. Open the page. Point at the left panel: skillc has already read this folder as Copilot CLI sees
   it. Nobody typed a tool list.
2. Click the example **fix-failing-test**, written with Copilot CLI's tool names (`grep`, `view`,
   `edit`, `bash`). ACHIEVABLE here and in Copilot CLI; IMPOSSIBLE in Claude Code (no `view`) and
   claude.ai (no `edit`, `grep`): profiles match tool names.
3. Click **book-a-table**: the opposite. It needs claude.ai's `ask_user_input_v0`.
4. Click the **edit** tool to switch it off. Only "this machine" flips to IMPOSSIBLE: settings decide.
   **Undo my changes**.
5. Click **post-release-note**: IMPOSSIBLE everywhere, no Slack tool. Type `slack_send_message` in
   *add a tool* and press **Add**: it becomes ACHIEVABLE here, as if a Slack server were connected.
6. Open **2 · A graph** and press **Load example** (`campus-building.trig`). The building is
   drawn: floors on top, then AHUs and VAVs, schedules and the policy, zones and rooms, points.
   skillc runs the built-in set-point and schedule-update verifiers at once.
7. Click `ex:sp13` in the list: its evidence path lights up in green (VAV, zone, rooms) and the
   panel shows what is missing (a BACnet reference). Click `ex:sp11` (verifiable) and `ex:zone31`
   (no schedule, no policy) to compare.
8. Pick **campus-sketch.txt · sketch** and **Load example**: the same kind of building, typed as
   whiteboard arrows, read without a model. Open the sketch box, delete the `BACnet` part of the SP-11
   line and press **Read this sketch**: SP-11 turns IMPOSSIBLE. With `--llm`, pick
   **campus-sketch.svg · picture** and **Read the picture**: a model writes the sketch text, which
   you review before skillc reads it.
9. Open **3 · Why skillc**. Pick a tool setup, then a case, and compare the three columns (below).

## 1 · My environment: what can an agent do here?

On load the page reads this folder as a GitHub Copilot CLI agent started here would see it
(`skillc.env.copilot.probe`):

* **Tools**: Copilot CLI's built-in tools, with this platform's shell (`powershell` on Windows,
  `bash` elsewhere). Reads, search and questions run without asking; shell commands and file
  writes ask first unless you saved an approval for this repository
  (`~/.copilot/permissions-config.json`).
* **MCP servers**: the built-in GitHub server and those in `~/.copilot/mcp-config.json`,
  `.mcp.json` and `.github/mcp.json`.
* **Credentials:** which of the usual names are set. Values are never read into the page.

One line under the panel says what was read and when (hover it for the files).

Pick an example skill or paste your own, and press **Check it here**. skillc compiles the text once
(no tool is assumed) and checks it against this machine and four published profiles side by side:

| skill | this machine | Copilot CLI | VS Code Copilot | Claude Code | claude.ai |
|---|---|---|---|---|---|
| `fix-failing-test` | ACHIEVABLE | ACHIEVABLE | IMPOSSIBLE: missing `grep`, `view` | IMPOSSIBLE: missing `view` | IMPOSSIBLE: missing `edit`, `grep` |
| `book-a-table` | IMPOSSIBLE | IMPOSSIBLE | IMPOSSIBLE | IMPOSSIBLE | ACHIEVABLE |
| `post-release-note` | IMPOSSIBLE: missing `slack_send_message` | IMPOSSIBLE | IMPOSSIBLE | IMPOSSIBLE | IMPOSSIBLE |

Profiles match tool **names**, so a skill written with one runtime's names is IMPOSSIBLE where the
names differ (VS Code Copilot calls them `grep_search` and `read_file`). Any runtime with a shell
grants `bash`, so Windows' `powershell` serves a skill that runs commands through Bash.

**Rows and columns.** Each row is a place the skill could run; "this machine" is your own Copilot
CLI in this folder, read automatically (it is not skillc). Each column is a checker:

| Column | Who decides | What it is given |
|---|---|---|
| **skillc** | the checker, no model | the compiled skill and the row's tools |
| **LLM** | a model, asked directly | the skill and, per row, the tool names; for this machine also which tools ask first, the MCP servers and the credential names set |
| **LLM + guiding skill** | the same model | the same facts, plus a guiding skill: start with what "finished" means, **look at the tools first**, match each step to a tool by name, then see **how the agent may interact** (asks first, denied, MCP servers, credentials), and answer UNKNOWN rather than guess |

The guiding skill is shown on the page under the table. Neither LLM sees skillc's answer. A cell
outlined in amber differs from skillc; the footer gives each LLM's tokens and time (skillc: 0
tokens). A what-if edit re-runs only skillc; press **Check it here** to ask the LLMs again. Tab 3
has the measured comparison, with each task really executed.

**Use it in your own Copilot sessions** (the panel's last section):

```bash
skillc check SKILL.md        # before you install a skill (Copilot CLI; --profile vscode-copilot for VS Code)
skillc reach SKILL.md        # what this folder allows, what is blocked, and how to unblock it
skillc monitor init          # writes .github/hooks/skillc.json: Copilot asks skillc before every tool call
```

**What-if.** Click a tool to switch it off, or add one (for example `slack_send_message`, as if a
Slack server were connected). Only the "this machine" row is re-checked. **Undo my changes**
restores what was read.

`UNKNOWN` means skillc could not read a goal from the text. That happens with a free-form prompt
such as "book me a flight". It never counts as permission. The example skills say what "finished"
means and list their tools and steps, which the deterministic reader needs.

## 2 · A graph: what can it answer?

1. **Load a graph**, in any of four forms. Pick an example and press **Load example**, or upload
   your own: an RDF file (Turtle, TriG, N-Triples, N-Quads or RDF/XML; JSON-LD is refused), a
   **scribble** of arrows or a **plain description** (`.txt`), or a **picture** of a sketch (PNG,
   JPEG, WebP or SVG). A scribble or description opens in an editable box: skillc reads it without
   a model, says line by line what it read, and lists every line it could not read (that line adds
   nothing). A picture is first turned into that text by a model (only with `--llm` and the
   opt-in), shown for you to review, then read the same way. The graph is drawn in rows: building and
   floors, equipment, schedules and policies, places, points, each coloured by kind. Classes, units,
   values and nested structures such as priority arrays are not drawn; they appear in a node's
   details when you click it.
2. **Check it.** Press **Check what the graph can establish**. With no workflow, skillc runs the
   built-in set-point and schedule-update verifiers. To check your own workflow, open **Your
   workflow** and paste it as you have it: a brief with "Evidence needed", a bullet list or a table.
3. **Read the result.** Each target gets `ACHIEVABLE` (every critical piece of evidence is in the
   graph) or `IMPOSSIBLE` with the evidence that is missing. Click a target, in the list or in the
   graph: the entities and links that prove its evidence light up in green, the target gets a green
   or red ring, and the side panel lists each piece of evidence with its graph path, or why it is
   missing. **How skillc read the workflow** shows how each line was mapped.

| Example | Form | What it has |
|---|---|---|
| `campus-building.trig` (default) | RDF graph | 3 floors, 3 AHUs, 9 VAVs, 9 zones, 18 rooms, 10 set points; 3 of 10 set points and 2 of 9 zones can be verified, and each other one misses something specific (limits, a BACnet reference, a schedule or an operating policy). Made by `examples/building-twin/make_campus.py`. |
| `demo-building.trig` | RDF graph | The small example from [`docs/TWIN.md`](../../docs/TWIN.md): Brick and RealEstateCore styles, an extra equipment hop, a vendor class defined only in an ontology graph. |
| `campus-sketch.txt` | scribble | A smaller campus as whiteboard arrows: 2 floors, 2 AHUs, 3 VAVs, 3 zones; SP-11 and Zone 11 verify, SP-12 has no limits, SP-21 no BACnet reference, Zones 12 and 21 no policy. |
| `campus-description.txt` | plain sentences | The same campus written as sentences; same verdicts. |
| `campus-sketch.svg` | picture | The same campus drawn on a whiteboard. Needs a model to read (`--llm`). |

This is `skillc twin explore` and `skillc twin check` (see [`docs/TWIN.md`](../../docs/TWIN.md)), which
accept the `.txt` forms too. All examples are made up; no tenant data.

## 3 · Why skillc: an LLM alone, an LLM with a guiding skill, and skillc

Choose **Tools the agent has** (a coding agent with GitHub Copilot CLI tools, a chat assistant with
claude.ai tools, or a finance agent of six role agents on Foundry), then a **Case**. Each case shows
the same prompt three ways:

1. **LLM alone**: the model gets the prompt and acts.
2. **LLM + a guiding skill**: the model is also told to check its tools and permissions first and
   to follow the rules, which is the best a prompt can do.
3. **skillc**: the real checker or monitor, run live on the page. For runtime cases it receives the
   same actions column 1 attempted, and every call after a refusal never runs.

| Setup | Case | What it shows |
|---|---|---|
| Coding agent | Post the release note to Slack | A guiding skill can stop honestly too; skillc decides before any run, without a model |
| Coding agent | Fix the failing test, then deploy to Vercel | A tool check passes (a shell exists), but a precondition (the account) fails late; skillc refuses the plan |
| Coding agent | A file tells the agent to force-push | A rule in the prompt can be overridden; skillc's refusal, as a Copilot hook, sits outside the model |
| Chat assistant | Fix a failing test from a chat window | The same skill belongs to one runtime and not another |
| Finance agent | Approval is skipped when the rule isn't in the prompt | **Measured** (126 runs on Foundry): without the policy sentence the bare agent delivered unapproved reports in 2 of 3 runs, with it 0 violations; skillc held the rule either way |
| Finance agent | Email the report to the CFO | The deliverable is refused before deployment; column 2 is measured |

Columns 1 and 2 are **replays**. "Measured" ones come from recorded runs
([`docs/HOSTED_AGENT_COMPARISON.md`](../../docs/HOSTED_AGENT_COMPARISON.md)); "illustrative" ones show
typical behaviour and are labelled as not being recordings. No model is called. The honest takeaway is
in the finance case: with the rule in the prompt, a strong model obeyed and skillc had nothing to do;
skillc matters when the prompt, a tool's check or the model is weaker than the rule. Cases are data in
`why_cases.json`.

### Fresh measurements, separate from the replays

**3 · Why skillc** now separates three sources: the illustrative/recorded case
replays, a **dated published comparison** from 22 October 2026, and **your latest
local measurements**. The published findings remain visible in a fresh checkout,
even without local run files. They explain the metric denominators, the difference
between abstention and false refusal, and the branching workflow's feasible parts.
Read the [full explanatory report](../../docs/LOCAL_ENVIRONMENT_BENCHMARK.md),
also linked directly from the app.

The local-measurements panel reads the newest `runs/*_here_benchmark/results.json`.
It displays plain LLM, environment-first guided LLM and SkillC accuracy, false stops,
false go decisions, early stops, independently verified runtime successes and provider
token usage, plus per-deliverable outcomes. Partial runs and inference errors remain
visible. These are not automatically the same run as the published reference.
Viewing either source never calls a model.

Run the offline checker and runtime oracle first:

```powershell
.\.venv\Scripts\python.exe scripts\benchmark_here.py --repeats 1
```

For a deliberate live comparison, configure the existing guarded provider with your own
endpoint and deployment, then opt in for this process:

```powershell
$env:AZURE_OPENAI_ENDPOINT = '<your Azure OpenAI endpoint>'
$env:SKILLC_ALLOW_MODEL_CALLS = '1'
try {
    .\.venv\Scripts\python.exe scripts\benchmark_here.py --live --provider azure-openai --model '<deployment>' --repeats 3
} finally {
    Remove-Item Env:SKILLC_ALLOW_MODEL_CALLS
}
```

Azure CLI sign-in or `AZURE_OPENAI_API_KEY` supplies authentication. Run
`.\.venv\Scripts\python.exe -m pytest tests\test_urlguard.py -q` before model inference.
Only fixed, allowlisted operations execute: local Git history, report generation, ZIP,
pandoc Word conversion, openpyxl export and parsing the repository's building graph.
No model-generated shell command, installation, deployment, email or cloud write can run.
Each case gets its own runtime oracle, which attempts the workflow even if preflight
stops, so an erroneous refusal is not counted as a correct stop.

These are seven newly authored practical workflows over real repository artifacts,
not recordings of production incidents. The building graph is synthetic. Programs and
modules are discovered automatically, but the operation contracts and workflow graph
are authored, not inferred from arbitrary prose. All arms have the same contracts and
access to the same discovery tool. The permission-denial case exercises an explicit
benchmark output-directory policy, not an observed OS ACL or cloud role. MCP configuration
is read without contacting servers; no live tool-list or authentication claim follows.

SkillC's intermediate-condition results, blockers and checker certificates are saved
beside the model transcripts, provider usage and output artifacts. The combined-handoff
case reports independently feasible branches even when the full goal is blocked. The
measured early-stop policy does not execute those branches. Zero model tokens apply to
this authored-graph preflight; they do not include general natural-language compaction.
The generated `REPORT.md` states these limits. A guided LLM may tie detection accuracy;
the benchmark must report that rather than assume SkillC wins.

## What it reads, and what it does not

* The first tab reads Copilot CLI's saved configuration, not a running session. A session's launch
  options (`--deny-tool`, `--available-tools`, `--excluded-tools`, `--allow-all`) are not recorded
  in any file, so they are reported as unknown. "Asks first" tools count as possible grants: a
  positive result is conditional on your approval, not a verified grant. Credential-variable
  presence likewise does not establish valid authentication or authorization.
* MCP servers' tools are not listed (no server is started), so they do not count. Add a tool by
  hand to try the what-if.
* Uploaded graphs are written to a temporary directory for parsing and deleted afterwards. JSON-LD
  is refused, because it can fetch remote contexts.

## API

* `GET /api/environment` (`?refresh=1` reads again): `runtime`, `captured`, `sources`, `tools`,
  `mcp`, `credentials`, `grants`, `settings` (the grants of each setting).
* `GET /api/samples`: the example skills, graph and workflow.
* `POST /api/check` `{"text", "machine": [tool, ...]?}`: `name`, `needs`, and `rows` with
  `setting`, `verdict`, `reason`, `detail`, `missing`.
* `POST /api/llm-check` (same body; only with `--llm` and the opt-in): `provider`, `model`,
  `guide`, and `arms.plain` / `arms.guided`, each with `rows` (`setting`, `verdict`, `missing`,
  `reason`), `input_tokens`, `output_tokens`, `ms` and `error`.
* `GET /api/why`: the arms, setups and cases. `POST /api/why/run` `{"id"}`: the live skillc column
  (`mode` static: `verdict`, `missing`; `mode` runtime: `plan_decision`, `plan_reason`, `steps`).
* `GET /api/benchmark`: latest local benchmark aggregates and case outcomes, or an explicit
  unavailable/error reason; never raw settings, credentials or model transcripts.
* `GET /benchmark-report`: the curated published report as readable plain-text Markdown.
* `POST /api/twin/graph` `{"graph", "filename", "tenant"?}`: `nodes` (`id`, `kind`, `types`,
  `details`), `edges` (`s`, `t`, `p`), `facts`, `truncated` (at most 800 entities are drawn), and
  for a `.txt` sketch `sketch` (`read`: line, text, meaning; `ignored`: line, text; `entities`).
* `POST /api/twin/transcribe` `{"image": base64, "mime"}` (only with `--llm` and the opt-in):
  `text` (the sketch, for review), `reading`, `input_tokens`, `output_tokens`, `ms`.
* `POST /api/twin/explore` `{"graph", "filename", "tenant"?}`: `text`.
* `POST /api/twin/check` `{"graph", "filename", "workflow", "tenant"?}`: `workflows`, each with
  `title`, `reading`, `results` (`target`, `verdict`, `missing`, `found`, `evidence` with each
  piece's `found` path lines or `note`) and `report`. An empty `workflow` runs the built-in verifiers.
