# skillc for hosted agents: difficulties and a proposal

**Status:** proposal (branch `gc/hosted_agent`). Nothing in this document is
implemented yet. The design is deliberately provider-neutral; the primary
target is **Microsoft Foundry Agent Service hosted agents**, and the same
design covers Claude Managed Agents and GitHub Copilot's cloud agent with
thinner adapters.

## 1. What skillc does today, and where it assumes a local machine

skillc answers one question: *is the goal of this SKILL.md / agent.md /
prompt achievable in capability context Γ?* Three mechanisms supply Γ:

| mechanism | where Γ comes from | assumption that breaks for a hosted agent |
|---|---|---|
| **profiles** (`--profile claude-code`, `vscode-copilot`, JSON) | a static tool list | the tool list of a hosted agent is not static; it is the union of the agent's own code and whatever the toolbox exposes to *this* identity |
| **environment probe + reach** (`skillc env probe --claude/--azure/--mcp`, `skillc reach`) | the machine skillc runs on: `~/.claude/settings.json`, `PATH`, importable modules, credential variable names, one HTTPS request per host, `.mcp.json`, the developer's `az login` | the agent runs in a per-session VM sandbox elsewhere; the developer's laptop tells you nothing about the sandbox's programs, egress, or identity |
| **runtime monitor** (`skillc monitor`, hooks `prompt/pre/post`) | Claude Code hook events on stdin, a transcript file, state in `.skillc/state.json` | there are no Claude Code hooks; the agent loop is the customer's own code (Agent Framework, LangGraph, Claude Agent SDK) |

Everything *inside* the trust boundary (the checker, the CE parser, grant
binding, reach) is already runtime-neutral and needs no change. The work is
entirely in how Γ is **observed** and how the monitor is **attached**.

## 2. What a hosted agent is (facts the design rests on)

From the Foundry documentation (hosted agents concept page, updated
2026-09-29):

* The agent is a **container image** in ACR. Each `create version` call makes
  an **immutable agent version**: image, CPU/memory, environment variables,
  protocols. One version serves the endpoint at a time.
* The sandbox is **per session, VM-isolated**, with a persistent `$HOME` and
  `/files` that survive idle and resume. Idle timeout 2 to 60 minutes;
  sessions are deleted after 30 days. Disk budget up to 20 GiB, 20 % reserved.
* Every hosted agent gets its **own Microsoft Entra agent identity** and a
  dedicated endpoint. The identity can call models and session storage by
  default; any other Azure resource needs an explicit RBAC assignment. When
  invoked from Teams/M365 with a user token, the agent may act **on behalf of
  the user** (OBO), so effective permissions depend on who called.
* Tools are not in the agent definition. They are reached through a
  **Toolbox MCP endpoint** in the project (Code Interpreter, Web Search, Azure
  AI Search, OpenAPI, MCP, A2A, **Skills**, ...), with consolidated auth
  (identity passthrough, agent identity, key).
* **Secrets are not to be put in env vars**; they come via connections and
  Key Vault.
* Egress may be **VNet-restricted** (network-isolated projects, customer VNet).
* Observability is **OpenTelemetry into Application Insights**, injected by
  the platform.

Claude Managed Agents are analogous: Anthropic runs the loop, tools execute
in a sandboxed container (or a self-hosted sandbox), the tool set is
declared (`agent_toolset_20260401` plus custom/MCP tools), and the Agent SDK
exposes `PreToolUse` / `PostToolUse` / `UserPromptSubmit` hooks with the same
event shapes skillc already consumes.

## 3. The difficulties, one by one

### D1. Two environments, not one

For a hosted agent Γ has a **control-plane half** (what the platform grants
the agent: identity, RBAC, toolbox tools, connections, VNet, sandbox size)
and a **data-plane half** (what the container can actually do: programs,
Python modules, writable paths, egress that really answers). Today's probe
conflates them because on a laptop they coincide. Neither half alone is
enough: RBAC says the identity may read a storage account, but only the
sandbox knows whether `azure-storage-blob` is importable and the endpoint is
reachable through the VNet.

### D2. The tool list is remote and identity-dependent

`env/mcp.py` lists tools only for **stdio** servers it can spawn; HTTP
servers are recorded as unknown. The toolbox is an **HTTP MCP endpoint behind
Entra auth**, and with identity passthrough the tools a given user can use
may differ from what the agent identity sees. Without a token-bearing HTTP
MCP client, every toolbox tool is "unknown", so no refutation can ever rest
on a missing tool.

### D3. Whose permissions?

`env/azure.py` probes *the signed-in principal* (`az login`). The relevant
principal is the **agent identity** (a different object id), and in OBO mode
it is **the end user**, who is not known at check time. Role assignments for
another principal can be listed if the developer has `Reader` on the scopes,
but OBO permissions are a genuine unknown and must stay three-valued.

### D4. Credentials are connections, not environment variables

`env/claude.py` models a credential as "variable NAME is set". In a hosted
agent that is the anti-pattern. A credential is a **connection** on the
project (Key Vault, storage, OpenAPI auth) bound to the agent identity. The
environment graph has no node for that today.

### D5. No hooks, no transcript, several frameworks

The monitor's logic (`Monitor.pre_action`, `post_action`, `observe_thinking`,
plan approval) is framework-neutral, but its only adapter is the Claude Code
hook protocol: JSON on stdin, `transcript_path` for reasoning text,
`permissionDecision` on stdout. A hosted agent's loop is Agent Framework,
LangGraph, Semantic Kernel, the Claude Agent SDK, or hand-written code. The
"thinking" signal must come from the framework's streamed events, not a
file.

### D6. Tool vocabulary

`TOOL_MAP` translates Claude Code tool names (`Bash`, `Write`, `WebFetch`)
to runtime-manifest tools. Hosted agents call `code_interpreter`,
`azure_ai_search`, OpenAPI operation ids, arbitrary MCP tool names. The map
must be **generated from the toolbox listing**, not hard-coded.

### D7. Software: immutable image, persistent `$HOME`

Runtime manifests say `software: installable | preinstalled | none`. A
hosted sandbox is in between: the image is immutable, but `pip install
--user` into `$HOME` works within a session (if egress to PyPI is allowed)
and is lost for a new session. The monitor's observation "No module named X
-> missing program" is right; the resolver's optimism ("absence is never
evidence, a registry is reachable") is wrong when the VNet blocks PyPI.

### D8. Egress cannot be measured from outside, and the probe refuses private addresses

`egress()` deliberately refuses hosts that resolve to private or loopback
addresses. Inside a VNet the whole point is to reach private endpoints. An
egress fact for a hosted agent is only trustworthy when measured **from
inside the sandbox**, and the safety rule needs an explicit "I am inside the
network" mode.

### D9. When is the check run, and against which version?

Versions are immutable and swapped atomically, so a snapshot is only valid
for one (agent, version) pair. There are three natural moments: before
`create version` (deploy gate), at session start (self-probe), and per tool
call (monitor). The watcher (`skillc env watch`) assumes a long-running
sibling process on a machine; on Foundry it must be a scheduled job.

### D10. Where skillc's state lives

`.skillc/state.json`, the plan file and snapshots assume a project directory
and file locks shared by hook processes. In the sandbox, `$HOME` is the only
persistent directory, is per session, and is restored onto *new* compute on
resume. The Foundry state store is the durable alternative.

### D11. Multi-agent delegation (A2A)

A toolbox A2A entry is a capability whose achievability is another agent's
problem. skillc has no notion of a capability that is itself a delegated
goal. (Out of scope for the first increment; noted so the schema leaves room.)

### D12. Packaging inside the image

skillc depends on `z3-solver` (native wheel, ~30 MB). That is fine for a
container, but the image must install skillc, and sandbox sizes start at
0.5 vCPU / 1 GiB, so the self-probe and monitor must stay cheap. They are:
no model calls, z3 only for the plan check.

## 4. Proposal

The guiding rule stays the one skillc already follows: **refutations rest
only on observed facts; anything not observed is an assumption, reported as
such.** Every item below adds a way to *observe* the hosted environment, or
a way to *attach* the monitor; none touches the checker.

### P0. Schema additions to `skillc.env/1` (small, backward compatible)

* `principal` gains `attrs.object_id`, `attrs.identity_mode` (`agent` | `obo`).
* new `service` types: `connection` (name, kind, auth mode; never a secret),
  `toolbox` (the MCP endpoint, `url` without query), `sandbox` (`cpu`,
  `memory_gib`, `disk_gib`, `idle_timeout_min`, `agent_version`).
* `scope` of level `path` already models `$HOME` and `/files`.
* `sources[]` gains `mode: "control-plane" | "data-plane"` so a report can
  say which half a fact came from, and `unknown` entries name the half that
  could not be read.

### P1. Control-plane adapter: `skillc env probe --foundry`

```
skillc env probe --foundry --project https://<acct>.services.ai.azure.com/api/projects/<proj> \
                 --agent <name>[:<version>] [--as-user]  -o env.json [--save-raw DIR]
```

Reads, read-only, with the developer's `az login` (or any
`DefaultAzureCredential`):

1. the agent and its current version: image reference, CPU/memory, idle
   timeout, protocols, **environment variable names only**;
2. the agent identity's object id, then its role assignments and deny
   assignments through the existing Azure adapter, parameterised by
   `--assignee` instead of "the signed-in principal";
3. the project's connections (kind and auth mode, no values);
4. the toolbox: `tools/list` over **HTTP MCP with a bearer token** (new
   `mcp.list_http_tools(url, token)`; paged like the stdio path). With
   `--as-user` the token is the developer's, which models identity
   passthrough for *that* user; otherwise the listing is attributed to the
   agent identity;
5. VNet configuration: whether the project is network-isolated and the
   outbound VNet, recorded as a fact that makes *public* egress **unknown**
   (not refused) until measured inside.

Everything is replayable offline via `--save-raw` / `--from-raw`, exactly
as the Azure adapter does today, so tests need no live project.

Prompt-based (declarative) Foundry agents are the easy case: the agent
definition carries the tool list directly, so step 4 reads it from the
definition and no MCP call is needed.

The same probe also emits a **generated profile**
(`skillc env profile env.json -o foundry-<agent>.json`) so the plain
`skillc check SKILL.md --profile foundry-<agent>.json` works for people who
only want the static verdict.

### P2. Data-plane self-probe: `skillc env probe --self`

Runs **inside the sandbox**, writes `skillc.env/1` to
`$HOME/.skillc/env/latest.json`, and never contacts anything the intent does
not name:

* platform, CPU count, memory and free disk (the sandbox facts);
* programs on `PATH`, importable modules, writable `$HOME` and `/files`;
* environment variable *names* (configuration, not secrets) and the
  presence of the App Insights connection string;
* egress to the hosts the intent needs, with `--inside-network` lifting the
  non-public-address refusal because private endpoints are the purpose;
* the toolbox from the inside: `tools/list` with the agent identity's token,
  which is the **authoritative** tool list for autonomous runs.

Three ways to trigger it, all optional:

* a CLI entrypoint in the image (`python -m skillc env probe --self`) for
  the deploy pipeline's smoke test;
* an Invocations route (`POST /invocations {"action": "skillc.probe"}`) for
  on-demand probing of a live version;
* a startup hook in the protocol library that probes once per session and
  caches the result in `$HOME`.

`skillc env merge control.json self.json` gives the full Γ. A fact present
in both halves must agree; a disagreement is reported, and the data-plane
value wins for programs, modules and egress, the control-plane value for
RBAC and connections.

### P3. Deploy gate

```
skillc gate agent/ --env env.json [--runtime foundry-hosted] [--json]
```

Walks the agent's instructions and every attached Skill (`SKILL.md`), runs
`skillc intent` + `skillc reach` for each against the merged environment,
and exits `0 / 1 / 3 / 2` like `skillc reach`. Packaged as a GitHub Actions
step and an `azd` pre-deploy hook so an `IMPOSSIBLE` skill cannot be shipped
in a new version. The report names the fix (the RBAC role at the scope, the
toolbox tool to connect, the host to allow in the VNet).

### P4. Runtime monitor as middleware (the main code change)

Split `monitor_hook.py` into a transport-neutral core and adapters:

* **core** (already mostly there): `Monitor.on_prompt(text)`,
  `on_reasoning(text)`, `pre_action(tool, input) -> Decision`,
  `post_action(tool, input, output) -> Decision`, `approve_plan(ce_text)`.
  The state backend becomes pluggable: file in `$HOME/.skillc` (default, it
  survives idle/resume) or the Foundry state store (durable across sessions).
* **adapters**, each a few dozen lines:
  * `skillc.monitor.claude_hooks`: the existing stdin/stdout protocol,
    unchanged; it also serves the Claude Agent SDK and Claude Managed Agents
    hooks, whose event shapes are the same.
  * `skillc.monitor.agent_framework`: a function-invocation middleware that
    calls `pre_action` before and `post_action` after every tool, and a
    chat middleware that feeds streamed assistant text to `on_reasoning`.
  * `skillc.monitor.langgraph`: a wrapper around the tool node.
  * `skillc.monitor.mcp`: `skillc monitor serve` exposes
    `skillc_plan`, `skillc_check_action`, `skillc_observe` as an MCP server
    (stdio in the container, or HTTP as a sidecar), so any framework can call
    it as a tool without a Python dependency.
* **tool map from the environment**: `Config.tool_map` is generated from the
  toolbox listing and the runtime manifest, not hard-coded. Unknown tool
  names are denied with "not a tool of this runtime", as today.
* **thinking signal**: the SDKs' streaming text is passed explicitly; the
  transcript-file path becomes one adapter's detail.
* A new runtime manifest `foundry-hosted.json` with `software:
  "session-installable"` (a fourth mode): a missing module is reachable only
  if the self-probe observed egress to the registry, and the resolver notes
  that the install does not survive the session.

### P5. Watcher as a scheduled job, verdicts as telemetry

`skillc env watch --once --foundry ...` already fits cron. Package it as a
Container Apps Job / Function on a timer that re-probes the control plane,
diffs, re-runs the watched intents and writes the report; the data-plane
half is refreshed by the startup hook of P2. Monitor decisions and gate
verdicts are emitted as OpenTelemetry events (`skillc.verdict`,
`skillc.decision`) so they land in the same Application Insights resource
the platform already wires up.

### P6. Later: A2A composition

Model an A2A toolbox entry as a capability with an `attrs.delegated_intent`;
`reach` treats it as achievable under the assumption "the delegate achieves
its goal" unless the delegate's own `skillc gate` report is attached, in
which case the assumption is discharged or the capability is withdrawn.

## 5. Order of work and what each step proves

| step | deliverable | proves |
|---|---|---|
| 1 | P0 schema + `foundry-hosted` manifest + generated profile | existing `check` works for a hosted agent from a static snapshot |
| 2 | P1 control-plane probe with `--from-raw` replay and tests on a recorded export | tool list, RBAC of the agent identity, connections observed; refutations possible |
| 3 | HTTP MCP `tools/list` with bearer token (used by P1 and P2) | toolbox tools stop being "unknown" |
| 4 | P2 self-probe + `merge` rules + `examples/hosted-agent/` (Agent Framework, Responses protocol, runs locally with the protocol library's dev server) | the two halves combine; egress and software facts come from inside |
| 5 | P4 core split + `claude_hooks` + `agent_framework` adapters, state in `$HOME` | the monitor gates a hosted agent's tool calls; live test like `scripts/monitor_live.py` but against the example container |
| 6 | P3 gate as a CI step and `azd` hook | an IMPOSSIBLE skill cannot ship |
| 7 | P5 job + OTel; P6 | operations view; delegation |

Steps 1 to 3 need no running container and can be fully tested from
recorded exports. Step 4 is where the real sandbox matters and is the first
thing to try live on the `foundary-tzuc06` project.

## 6. What stays assumed, never refuted

* **OBO permissions**: without a user token the user's RBAC is unknown; the
  report says "achievable if the invoking user holds role R at scope S".
* **Toolbox listing drift**: a tool observed at probe time may be removed
  later; the monitor's per-call check catches it, the snapshot does not.
* **Egress measured only once per session** by the self-probe; a VNet rule
  changed mid-session is caught by the monitor's post-action observations
  (resolver and 403 errors), as today.
* **The sandbox is honest**: the self-probe runs as the agent identity inside
  the agent's own container; it can only misreport its own environment,
  which hurts only itself.

## 7. Open questions to settle before step 2

1. Exact SDK surface for reading an agent version and its toolbox endpoint
   (`azure-ai-projects` / `az` CLI). The design assumes read-only calls
   exist for: agent + version, project connections, toolbox URL. Verify
   names against the installed SDK before writing the adapter.
2. Whether identity-passthrough tool listings should be modelled per user
   (one environment file per user) or as a single environment with the
   user-dependent tools marked `assumed`. Proposed: the latter by default,
   `--as-user` for the former.
3. State backend default for the monitor: `$HOME/.skillc` (zero
   configuration, per session) versus the state store (durable, needs the
   project endpoint). Proposed: `$HOME` by default, state store opt-in.

## Sources

* Hosted agents in Foundry Agent Service:
  https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/hosted-agents
* Foundry hosted agents with Microsoft Agent Framework:
  https://learn.microsoft.com/en-us/agent-framework/hosting/foundry-hosted-agent
* Hosted MCP tools (Agent Framework):
  https://learn.microsoft.com/en-us/agent-framework/agents/tools/hosted-mcp-tools
* Claude Managed Agents overview:
  https://platform.claude.com/docs/en/managed-agents/overview
* Claude Agent SDK overview (hook events):
  https://code.claude.com/docs/en/agent-sdk/overview
