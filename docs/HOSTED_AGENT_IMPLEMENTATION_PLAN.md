# skillc inside a Foundry hosted agent: implementation plan

**Status:** plan (branch `gc/hosted_agent`), 2026-10-07. Companion to
`docs/HOSTED_AGENT.md`, which holds the investigation; this document holds
the decisions and the work, in order, with what "done" means for each step.

## 0. Decision: no fork of Agent Framework

We do **not** fork `microsoft/agent-framework`. skillc ships its own
middleware package that plugs into the framework's public extension point.

Why a fork is the wrong tool here:

| concern | fork | plug-in (chosen) |
|---|---|---|
| extension point | not needed: `Agent(middleware=[...])`, `FunctionMiddleware`, `AgentMiddleware`, `ChatMiddleware` are public and documented, and denial by `context.result` + skipping `call_next()` (or `MiddlewareTermination`) is the documented guardrail pattern | uses exactly that |
| release cadence | `agent-framework-foundry-hosting` is prerelease and moves weekly; a fork must rebase constantly | pin a version range, isolate imports in one adapter module |
| deployment | `azd deploy` in `code` mode does a **remote build** from `requirements.txt`; a fork means a git URL dependency or a private wheel in every hosted agent | `pip install "skillc[agent-framework]"` from PyPI (or a private feed), one line |
| trust boundary | a fork puts skillc *inside* the framework the agent runs on; a bug in skillc becomes a bug in the agent loop | skillc stays a dependency the agent author opts into, fail-open by design |
| contribution | a long-lived fork diverges | if an extension point is missing (see risk R2), the fix is an **upstream pull request**, not a fork |

Dependency direction, fixed: **skillc depends on Agent Framework, never the
reverse.** The core package keeps its two dependencies (`z3-solver`,
`pyyaml`); everything Foundry- or framework-specific is an optional extra.

## 1. Target architecture

```
azd project (the build unit)
├── azure.yaml ──────► skillc env from-azd ──► declared Γ (assumptions)
│     hooks.predeploy: skillc gate . ─────────► IMPOSSIBLE intent ⇒ azd deploy stops
├── skills/*.md, agent instructions ─────────► intent artifacts (skillc intent)
└── src/<agent>/main.py
      Agent(client=FoundryChatClient(...),
            tools=[toolbox MCP tools, ..., skillc_write_plan],
            middleware=[SkillcAgentMiddleware(), SkillcFunctionMiddleware()])
      ResponsesHostServer(agent).run()

runtime (per-session VM sandbox)
  $HOME/.skillc/<session>/state.json      monitor state, survives idle/resume
  tools/list from the toolbox at startup  observed Γ, builds the tool map
  skillc env probe --self (optional)      programs, modules, egress from inside
  OpenTelemetry events                    skillc.verdict / skillc.decision → App Insights
```

Three attachment points, nothing else:

1. **Scaffold time**: `azure.yaml` → declared environment → `skillc check` / `reach`, offline.
2. **Deploy time**: `azd` `predeploy` hook → `skillc gate` → exit code stops a bad version.
3. **Run time**: two middleware classes in `main.py` → plan gate, action gate, observations.

## 2. Work packages

Each package lists goal, files, behaviour, tests, and the exit criterion.
Order matters: WP0 before anything, WP1 to WP3 can be parallel, WP4 needs
WP1 to WP3, WP5 and WP6 are independent of WP4 but come after it in value.

### WP0. Spike: confirm the four facts the adapter rests on (1 day)

No skillc code. A throw-away script against the `foundary-tzuc06` project
(or any Foundry project with a chat deployment), results written to
`docs/HOSTED_AGENT.md` section 2b.

| fact to confirm | how | if false |
|---|---|---|
| F1 function middleware fires for toolbox tools consumed client-side (`MCPStreamableHTTPTool` / `FoundryToolbox`) | agent with a toolbox and a logging `FunctionMiddleware`; call a toolbox tool | fall back to a chat middleware that inspects tool-call content blocks before they are dispatched |
| F2 a denied call (`context.result` set, `call_next()` skipped) reaches the model as the tool result and the model re-plans | deny every call once; check the next model turn mentions the reason | use `MiddlewareTermination(result=...)`; if that leaves history inconsistent, deny by rewriting arguments to a no-op |
| F3 `context.arguments` is a pydantic model whose `model_dump()` gives the tool input; `context.function.name` is the tool name | print | adapt the mapping |
| F4 the agent's own tool list (names) is reachable at startup after the toolbox connects | inspect `agent.tools` or the MCP tool's function list | build the map lazily on first call |

Also note whether the newer **Agent Hooks** API ("fail-closed control
boundary spanning agent, chat and function middleware", linked from the
middleware guide) is stable enough to prefer over plain middleware. Default:
plain middleware, because it is GA-documented and framework-neutral.

Exit: a short table in the doc with F1 to F4 answered, with the installed
package versions.

### WP1. Monitor core: finish making it transport-neutral (2 days)

Files: `src/skillc/monitor.py`, `src/skillc/data/runtimes/foundry-hosted.json`,
`src/skillc/frontend/runtime.py`.

* `Monitor.on_prompt(text) -> list[str]`: the once-per-session instructions
  (with the plan tool's name) plus the intent-check gaps; used by all three
  adapters (Claude hooks, Copilot hooks, Agent Framework).
* `Monitor.on_reasoning(text) -> Decision`: alias of `observe_thinking`.
* `tool_map_from_names(names, runtime) -> dict`: builds `Config.tool_map`
  from a list of tool names using a small normaliser (`code_interpreter` →
  `bash`-like execute, `web_search`, `web_fetch`, `azure_ai_search` →
  `search`, MCP names kept as-is) and the runtime manifest's vocabulary.
  Unknown names stay unmapped and are therefore denied as "not a tool of
  this runtime", as today.
* State scoping: `Config.state_file` may contain `{session}`; the adapter
  fills it with `FOUNDRY_AGENT_SESSION_ID` (or the Agent Framework session id).
* Runtime manifest `foundry-hosted.json`: tools `code_interpreter`,
  `web_search`, `web_fetch`, `search`, `mcp`, `openapi`, `a2a`; grants
  `linux`, `local_filesystem`, `app_insights`; lacks shell on the host,
  user conversation unless `ask_user` exists; `software:
  "session-installable"`, a fourth mode in `resolve_software`: a missing
  module is reachable only when egress to the registry has been observed,
  and the resolver's note says the install does not survive the session.
* Fail-open contract documented on `Monitor`: a `MonitorError` is never
  raised across an adapter boundary; adapters catch, log, allow.

Tests: extend `tests/test_monitor.py` (tool map builder, session-scoped
state path, `session-installable` resolution). All existing tests stay green.

Exit: `Monitor` has no reference to Claude Code or Copilot tool names
outside the two hook adapters.

### WP2. The Agent Framework adapter (3 days)

New package `src/skillc/integrations/agent_framework.py`, optional extra
`skillc[agent-framework]` → `agent-framework-core>=<pinned>,<next-minor>`.
Imports of `agent_framework` happen inside this module only.

Public API (small on purpose):

```python
from skillc.integrations.agent_framework import skillc_monitor

monitor_mw, monitor_tools = skillc_monitor(
    runtime="foundry-hosted",            # or a manifest path
    root=Path.home() / ".skillc",        # state survives idle/resume
    prohibited=[...],                    # optional Rule dicts
    thinking="warn",                     # stop | warn | off
)
agent = Agent(client=client, instructions=..., tools=[*toolbox_tools, *monitor_tools],
              middleware=[*monitor_mw])
```

Behaviour:

* `SkillcFunctionMiddleware(FunctionMiddleware)`:
  `pre_action(context.function.name, context.arguments.model_dump())`.
  On DENY: `context.result = {"skillc": "blocked", "reason": d.reason}`;
  return without `call_next()`. We do **not** set `terminate`, so history
  stays consistent and the model gets a normal tool result it can act on.
  On ALLOW: `await call_next()`, then
  `post_action(name, args, str(context.result))`; a WARN/DENY appends a
  `"\n\nskillc: ..."` note to a string result or a `"skillc"` key to a dict
  result, so the model sees the observation.
* `SkillcAgentMiddleware(AgentMiddleware)`: before `call_next()`, runs
  `on_prompt(last user message)` and, if there is anything to say, appends a
  `Message(role="user", contents=[...])` carrying the skillc instructions
  (the framework has no system-message injection for middleware; a user-role
  note is the documented way to add context). After `call_next()`, scans the
  response text with `on_reasoning` when `context.stream` is false; when
  streaming, wraps the update generator to accumulate text and scan at the
  end. The result is **observe-only in v1** (it can revoke the plan for the
  next action; it never rewrites a response).
* `skillc_write_plan(plan: str) -> str`: a `@tool` the agent calls to submit
  its Controlled English plan; it returns the approval text or the
  refutation. This replaces the file write of the hook adapters, because a
  hosted agent has no file tool unless given one. The plan is also stored in
  the state file.
* Tool map: built from the names of `agent.tools` (and the MCP tool's
  functions after connection) on first use, then cached in state.
* Fail-open: every adapter entry point is wrapped; an internal exception
  logs a warning (and an OTel event when available) and allows the call.
* Repeated-denial guard: after N identical denials in one session (default
  5), the reason changes to "stop and tell the user what is missing", so a
  looping model does not burn the turn budget.

Tests (`tests/test_agent_framework_adapter.py`, skipped when the extra is
not installed): a fake chat client that emits scripted tool calls (the
framework exposes a `FunctionInvokingChatClient`-style path we can drive
with a minimal `BaseChatClient` stub); scenarios: no plan → deny; plan via
tool → approved; disallowed tool → deny; `command not found` in a result →
observation; prohibited pattern in response text → plan revoked.

Exit: the four scenarios pass offline; `ruff` clean; the module imports
only when the extra is present.

### WP3. Declared environment and the deploy gate (3 days)

Files: `src/skillc/env/azd.py`, `src/skillc/cli.py` (`env from-azd`,
`gate`), tests with fixture `azure.yaml` files copied from
`foundry-samples` (attributed in `tests/fixtures/azd/README.md`).

* `env from-azd azure.yaml -o env.json`: deterministic walk of `services`
  as specified in `HOSTED_AGENT.md` P1a; every fact `declared`; `$ref`
  includes resolved relative to the file; `${VAR}` left unresolved and
  recorded as an unknown named value; unknown `tools[].type` recorded as
  unknown, never refused.
* `gate DIR --declared azure.yaml [--env observed.json]`: finds intent
  artifacts (agent `instructions` if in a file, every `azure.ai.skill`
  `instructions`, `skills/*.md`), runs `intent` + `reach` per artifact
  against `merge(declared, observed)`, prints one report, exits `0/1/3/2`.
  `--json` for CI. A fix list names the `azure.yaml` edit (tool type to add
  to the toolbox, connection to declare, network mode to relax).
* `azure.yaml` snippet printed by `skillc gate --install-hook`:
  ```yaml
  hooks:
    predeploy:
      shell: sh
      run: skillc gate . --declared azure.yaml --env .skillc/env/latest.json
  ```

Exit: the three sample projects (`01-basic`, `04-foundry-toolbox`, a
LangGraph sample) produce a sensible declared environment; a skill that
needs `azure_ai_search` is ACHIEVABLE only in the project whose toolbox
declares it.

### WP4. Example hosted agent, local run, first live deploy (3 days)

Files: `examples/hosted-agent/` with `azure.yaml` (toolbox with
`web_search` + Microsoft Learn MCP, the `predeploy` hook, one
`azure.ai.skill`), `src/agent/main.py` (Agent Framework + `skillc_monitor`),
`requirements.txt` (`skillc[agent-framework]`, pinned), `skills/*.md`
(one achievable, one impossible on purpose), `README.md`.

Sequence, strictly in this order:

1. `azd ai agent init` from the sample, then add skillc; `skillc env from-azd`
   and `skillc gate` run green locally.
2. `azd provision` against the existing `foundary-tzuc06` project (no new
   project).
3. `azd ai agent run` + `azd ai agent invoke --local` with four prompts
   mirroring `scripts/monitor_live.py`: achievable, impossible deliverable,
   prohibited effect, impossible discovered during the run. Record the
   transcripts under `runs/<date>_hosted_agent_local/`.
4. Flip the impossible skill in, confirm `azd deploy` is stopped by the
   hook; flip it out, `azd deploy`, `azd ai agent invoke` the four prompts
   again; `azd ai agent monitor --follow` for the skillc log lines.
5. Write the results into `docs/HOSTED_AGENT.md` as a "Live test" section
   like the one in `RUNTIME_MONITOR.md`.

Exit: the deployed agent refuses a disallowed tool call with skillc's
reason, visible in the Responses output and in App Insights.

### WP5. Control-plane probe (4 days)

Optional extra `skillc[foundry]` → `azure-ai-projects>=2.3.0`,
`azure-identity`. `env probe --foundry --project URL --agent NAME[:VERSION]`:
`agents.get`, `agents.get_version` (image or code configuration, cpu,
memory, env var names, protocols), `toolboxes` (list, get version),
connections, the agent identity's object id → existing Azure adapter with
`--assignee`; HTTP MCP `tools/list` against the toolbox endpoint with a
token for `https://ai.azure.com/.default` (new `mcp.list_http_tools`).
`--save-raw` / `--from-raw` as the Azure adapter does, so tests replay a
recorded export and no test needs Azure.

Exit: `env diff declared.json observed.json` shows exactly the facts the
probe promoted from assumption to observation.

### WP6. Self-probe, telemetry, watcher (after WP4)

`env probe --self --inside-network` run from the container (CLI entry point
and an optional Invocations route); merge rules (data plane wins for
programs, modules, egress; control plane for RBAC, connections); OTel
events `skillc.verdict` and `skillc.decision` through the injected App
Insights connection string; `env watch --once --foundry` packaged as a
timer job.

## 3. Packaging and deployment rules

* `pyproject.toml` extras: `agent-framework = ["agent-framework-core>=X,<Y"]`,
  `foundry = ["azure-ai-projects>=2.3.0", "azure-identity>=1.17"]`. Core
  dependencies unchanged.
* Publish skillc to PyPI (or the organisation's private feed) before WP4
  step 4: the remote build resolves `requirements.txt` from an index, not
  from a git URL.
* `z3-solver` is a 30 MB wheel; it fits the 0.5 vCPU / 1 GiB tier and z3
  runs only at plan time. Measure cold start in WP4 and record it.
* skillc makes **no network calls** from inside the agent except the
  optional self-probe, and reads **no secrets** (names only).
* Hosted-agent state lives in `$HOME/.skillc/<session>/`; nothing is written
  to the image or `/files`.
* Versioning: the adapter module records the `agent_framework` version it
  was tested with and warns once if the installed version is outside the
  range.

## 4. Risks and mitigations

| id | risk | mitigation |
|---|---|---|
| R1 | Agent Framework prerelease API changes break the adapter | one adapter module, pinned range, CI job that installs the latest prerelease nightly and runs the adapter tests |
| R2 | toolbox tools executed **server-side** by the model service bypass middleware | documented limit; the example consumes the toolbox client-side; recommend `require_approval` for server-side tools; if demand exists, open an upstream issue for a hook on hosted tool calls |
| R3 | tool names differ per toolbox version | map built from the live `tools/list` at startup, cached per session, rebuilt on a cache miss |
| R4 | a denied model loops on the same call | repeated-denial guard (WP2) and the plan tool's explicit "stop and report" instruction |
| R5 | streaming responses make reasoning scans late | observe-only in v1; the action gate is per call and does not depend on it |
| R6 | `terminate` leaves history inconsistent | never used; denial is a normal tool result |
| R7 | skillc bug stops a production agent | fail-open everywhere, logged and traced; `SKILLC_MONITOR=off` env switch |
| R8 | remote build cannot fetch skillc | publish to an index first; fall back to `container` deploy mode with a Dockerfile that installs from a wheel |

## 5. Timeline and ownership

| package | effort | depends on |
|---|---|---|
| WP0 spike | 1 day | a Foundry project |
| WP1 core | 2 days | none |
| WP2 adapter | 3 days | WP0, WP1 |
| WP3 declared env + gate | 3 days | none |
| WP4 example + live | 3 days | WP1 to WP3, PyPI publish |
| WP5 control-plane probe | 4 days | WP3 |
| WP6 self-probe, OTel, watcher | later | WP4 |

About three weeks of focused work to a live, gated, monitored hosted agent
(WP0 to WP4), with WP5 and WP6 following.

## 6. Governance

* Branch `gc/hosted_agent`; one pull request per work package; upstream to
  `ginaecho`, then downstream to the Microsoft account repository and
  `eag-innovation` under the usual rule.
* Licences: skillc MIT, Agent Framework MIT; no code is copied from the
  framework, only imported.
* Anything we find missing in the framework becomes an issue or pull
  request on `microsoft/agent-framework`, referenced from this document.
