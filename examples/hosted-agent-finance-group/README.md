# Quarterly Finance Report as a group of Foundry hosted agents

The six roles of the finance protocol (Fetcher, ExpenseAnalyst, RevenueAnalyst,
TaxSpecialist, TaxVerifier, Writer) run as **six** Microsoft Foundry hosted
agents that talk to each other over A2A. There is no coordinator: the user
invokes `finance-fetcher`, and the protocol's messages travel as A2A requests
and replies between the agents. Each agent has its own Entra instance
identity, so "only TaxVerifier approves" is a property of the deployment (the
approval tools exist only in `finance-tax-verifier`'s process) and not of a
prompt. The single-agent deployment of the same use case is
`../hosted-agent-finance/`; this example keeps its tools, its pack and its
data and changes only the deployment shape.

```
examples/hosted-agent-finance-group/
  azure.yaml                     1 toolbox, 10 RemoteA2A connections, 6 a2a toolboxes,
                                 6 skills, 6 hosted agents (same code, ROLE differs)
  skills/<Role>.md               one azure.ai.skill per role (the intent artifacts), written
                                 for the request/reply call chain of section 2
  skills-minimal/<Role>.md       the minimal-instruction variant (SKILLS_VARIANT=skills-minimal)
  protocol/quarterly_finance_report.ce   the pack, unchanged from the single example (header aside)
  data/2026-Q{2,3,4}.csv         the quarters (Q3 = high branch, Q2 = standard, Q4 = injected note)
  src/finance-agent-group/main.py        one Agent Framework agent per ROLE + A2AAgent edges
                                         + skillc middleware + the receive bridge
  scripts/grant_a2a.sh           Foundry Agent Consumer for every caller identity (after azd deploy)
  scripts/run_group.sh           invoke finance-fetcher with the Q3 request and save the answer
```

## 1. Architecture

* **One source, six agents.** `src/finance-agent-group/main.py` builds one
  `Agent` whose role is the environment value `ROLE`. The agent's instructions
  are `skills/<ROLE>.md` (staged by the predeploy hook; built-in fallback), its
  function tools are exactly the single example's for that role (copied, same
  names and semantics), and it has one **A2A tool per outgoing edge** of its
  local type, named after the callee role (`RevenueAnalyst`, `Writer`, ...).
* **A2A edges in code.** Each A2A tool is an `agent_framework.a2a.A2AAgent`
  with `url = ${FOUNDRY_PROJECT_ENDPOINT}/agents/<callee-service>/endpoint/protocols/a2a`
  (the callee's A2A base path, deterministic from its service name), exposed
  through `A2AAgent.as_tool(name=<Callee>, description=...)` (confirmed
  present on `A2AAgent`, inherited from `BaseAgent`). Authentication is a
  bearer token from `azure.identity.aio.DefaultAzureCredential` for the scope
  `https://ai.azure.com/.default`, which inside the sandbox is the agent's
  **own instance identity**; it is added by an `AuthInterceptor` subclass that
  sets `Authorization` unconditionally (the stock interceptor only adds it
  when the agent card declares security schemes, and a URL-only card declares
  none). `A2A_FETCH_CARD=1` additionally resolves the card from
  `.../agentCard/v1.0` with `a2a.client.A2ACardResolver(..., agent_card_path="agentCard/v1.0")`
  at startup (diagnostic; the minimal card is enough to call).
* **Serving.** `ResponsesHostServer(agent).run()` on `$PORT`; every agent
  exposes `responses` and `a2a` on its endpoint (incoming A2A requires the
  Responses protocol). `python main.py --check` builds the role without
  network and prints its tools, edges and the messages it sends and receives.
* **skillc.** The same guarded import as the single example
  (`from skillc.integrations.agent_framework import skillc_monitor`), one
  monitor per process with `runtime="foundry-hosted"`, the pack as the
  pre-approved plan (`skillc_plan.ce`, staged by the hook) and
  `agent_tools=<the callee roles this agent calls>`; `middleware_for(ROLE)`
  enforces the Tool's owner and precondition. `SKILLC_MONITOR=off` disables
  it. See section 5 for the receive bridge the group needs on top.

The table of tools, owners and effects is the single example's (`../hosted-agent-finance/README.md`, section 1); the pack is identical.

## 2. The protocol as requests and replies

A2A is request/reply, text only, one task per call. The global protocol is
asynchronous message passing. The mapping used here nests the calls so that
**the request carries the protocol message and the reply carries the next
message back**; every message is written on a line starting with its label in
square brackets (`[RawRevenueData] 72000.00`), which is what the skills ask
for and what the receive bridge reads.

```
user ──Responses──▶ Fetcher
                      │ fetch_financials
                      ├──A2A [RawExpenseData]──────────────▶ ExpenseAnalyst ─ analyze_expenses
                      │◀── reply [ExpenseData] [ExpenseAnalysis] ──┘
                      └──A2A [RawRevenueData] [ExpenseData] [ExpenseAnalysis] ──▶ RevenueAnalyst
                                                                                   │ classify_revenue
                                     high:  ┌──A2A [NotifyTaxSpecialist]──────────┤
                                            │  TaxSpecialist: lookup_tax_rules, audit_high_revenue
                                            └──reply [AuditReport]───────────────▶│
                                            ┌──A2A [HighRevenueNotification] [AuditReport]──┤
                                            │  TaxVerifier: approve_audited                 │
                                            └──reply [Approval]──────────────────▶│
                                     standard: A2A [NotifyStandardRole] → TaxSpecialist (reply [Acknowledged])
                                               A2A [StandardRevenueNotification] → TaxVerifier: approve_standard → reply [Approval]
                                                                                   │ write_revenue_analysis
                                            ┌──A2A [HighBranchNotification | StandardBranchNotification]
                                            │       [ExpenseAnalysis] [FinalRevenueAnalysis]──▶ Writer
                                            │  Writer: compose_report, deliver_report
                                            └──reply [GenerateReport]────────────▶│
user ◀── [GenerateReport] ── Fetcher ◀────── reply [GenerateReport] ───────────────┘
```

**The one semantic difference from the asynchronous MPST protocol**: a
message whose sender has nothing left to do in the branch is not a separate
call but **the reply** of the call that triggered it. `Writer -> Fetcher :
GenerateReport` is Writer's reply to RevenueAnalyst, relayed in
RevenueAnalyst's reply to Fetcher; likewise `TaxVerifier -> RevenueAnalyst :
Approval` is TaxVerifier's reply, `TaxSpecialist -> TaxVerifier :
AuditReport` is TaxSpecialist's reply (relayed by RevenueAnalyst in its
request to TaxVerifier), and `ExpenseAnalyst -> RevenueAnalyst : ExpenseData`
/ `ExpenseAnalyst -> Writer : ExpenseAnalysis` are ExpenseAnalyst's reply
(relayed by Fetcher, then RevenueAnalyst). Two consequences follow: Fetcher's
two causally independent sends are reordered (ExpenseAnalyst first, so that
the RevenueAnalyst request can carry the expense results), and
RevenueAnalyst's branch notification to Writer is folded into its single
Writer call together with `FinalRevenueAnalysis` (a second Writer request
would have to hold state across requests). The relayed messages keep their
sender's label, so each role's skill still names exactly the labels of its
projection. The full mapping is the `MESSAGES` table in `main.py`.

### The ten edges

| # | edge (caller -> callee) | message(s) | carried by | connection (`azure.yaml`) |
|---|---|---|---|---|
| 1 | Fetcher -> RevenueAnalyst | RawRevenueData (+ relayed ExpenseData, ExpenseAnalysis) | request | `fetcher-to-revenue-analyst` |
| 2 | Fetcher -> ExpenseAnalyst | RawExpenseData | request | `fetcher-to-expense-analyst` |
| 3 | ExpenseAnalyst -> RevenueAnalyst | ExpenseData | reply to Fetcher, relayed | `expense-analyst-to-revenue-analyst` |
| 4 | ExpenseAnalyst -> Writer | ExpenseAnalysis | reply to Fetcher, relayed twice | `expense-analyst-to-writer` |
| 5 | RevenueAnalyst -> TaxVerifier | HighRevenueNotification (+ relayed AuditReport) or StandardRevenueNotification | request | `revenue-analyst-to-tax-verifier` |
| 6 | RevenueAnalyst -> Writer | HighBranchNotification or StandardBranchNotification, FinalRevenueAnalysis (+ relayed ExpenseAnalysis) | request | `revenue-analyst-to-writer` |
| 7 | RevenueAnalyst -> TaxSpecialist | NotifyTaxSpecialist or NotifyStandardRole | request | `revenue-analyst-to-tax-specialist` |
| 8 | TaxSpecialist -> TaxVerifier | AuditReport | reply to RevenueAnalyst, relayed | `tax-specialist-to-tax-verifier` |
| 9 | TaxVerifier -> RevenueAnalyst | Approval | reply | `tax-verifier-to-revenue-analyst` |
| 10 | Writer -> Fetcher | GenerateReport | reply to RevenueAnalyst, relayed | `writer-to-fetcher` |

Every edge is declared (connection, `a2a` toolbox entry, `uses` on the
caller) and every caller has the A2A tool, including edges 3, 4, 8, 9 and 10
whose message travels in a reply: the declared topology is the protocol's,
and the skill of each such role says that its reply is the message and the
tool is not called. The toolbox `a2a` entries are declarations only; the code
calls `A2AAgent` directly.

## 3. Deploying

```console
$ azd env new finance-group
$ azd env set FOUNDRY_PROJECT_ENDPOINT https://<account>.services.ai.azure.com/api/projects/<project>
$ azd env set AZURE_AI_PROJECT_ID /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>
$ azd env set FOUNDRY_MODEL_NAME gpt-5.4; azd env set SKILLC_MONITOR on
$ azd provision --no-prompt        # toolboxes, connections and skills on the existing project
$ azd deploy --no-prompt           # predeploy hook (stage + gate), then six agent versions
$ sh scripts/grant_a2a.sh          # Foundry Agent Consumer for each caller's instance identity
$ azd ai agent invoke finance-fetcher "Produce the quarterly finance report for 2026-Q3. ..." --new-session
$ sh scripts/run_group.sh group 3  # the same, saved under ../../runs/<date>_group/group/
$ azd ai agent monitor finance-revenue-analyst --follow
```

The predeploy hook stages `skills/` (`SKILLS_VARIANT=skills-minimal` for the
minimal arm), `data/`, the vendored `skillc` (`../../src/skillc`) and the pack
as `skillc_plan.ce` into `src/finance-agent-group/` (the only folder that is
uploaded, once per agent), then runs the gate: `skillc gate . --declared azure.yaml`. The three
stumbling blocks of the single example's deploy log
(`AZURE_AI_PROJECT_ID` required, azd's own sign-in, stray `AZURE_*` machine
variables) apply unchanged.

`scripts/grant_a2a.sh` reads `AGENT_<SERVICE>_INSTANCE_IDENTITY_PRINCIPAL_ID`
for every caller from `azd env get-values` (falling back to `azd ai agent
show`), and creates one assignment of Foundry Agent Consumer
(`eed3b665-ab3a-47b6-8f48-c9382fb1dad6`) per caller on the **project** scope
(`AZURE_AI_PROJECT_ID`), skipping the ones that exist. The per-agent
alternative (one assignment per edge on the callee agent's resource) is the
tighter one and is discussed in the script's header.

## 4. What skillc checks

| moment | command | what is decided | status |
|---|---|---|---|
| offline | `skillc check protocol/quarterly_finance_report.ce` | the pack is achievable, the branch is realizable, TaxVerifier's behaviour conforms | run 2026-10-08: ACHIEVABLE (the pack is the single example's; `lookup_tax_rules` runs `via code_interpreter` there since 2026-10-08 because the base `azure.yaml` declares no `azure_ai_search`, and the gate refuses a pack whose Tool needs an undeclared runtime tool) |
| offline | `skillc env from-azd azure.yaml --json` | the declared environment: 6 principals (one per agent, identity mode `agent`), 10 `RemoteA2A` connections (`AgenticIdentityToken`, audience `https://ai.azure.com`), 7 toolboxes (`finance-tools` + 6 a2a toolboxes with 10 `a2a` tool nodes naming their connection), `responses 2.0.0` on every principal, env names only | run 2026-10-08: loads, 37 nodes (mcp_server 7, principal 6, scope 1, service 11, tool 12), 12 edges; the six `skills/*.md` reported as intent artifacts |
| offline | `skillc gate . --declared azure.yaml` | **topology against the protocol**: every `A tells B L` needs a `RemoteA2A` connection targeting B, an `a2a` entry in a toolbox A uses naming that connection, and `a2a` on B's endpoint; a missing edge refutes that message with the fix. The gate maps a protocol role to an agent by the agent's name or by the `azure.ai.skill` (`<Role>.md`) the agent `uses`, which is why every agent here `uses` its skill service | run 2026-10-08: pack ACHIEVABLE via `code_interpreter`, `write`; six skills ACHIEVABLE; topology: 10 of 10 edges ACHIEVABLE, each "assuming the identity of agent A holds Foundry Agent Consumer on agent B" (an earlier gate version resolved an edge's connection by callee only and refused four edges; fixed the same day) |
| offline | gate | **authorization**: Foundry Agent Consumer for A's identity on B is declared nowhere in `azure.yaml`, so each edge is "achievable if" the assignment exists (`scripts/grant_a2a.sh`) | reported as an assumption per edge by the gate; `skillc env probe --foundry` turns it into an observation |
| `azd deploy` | the predeploy hook | refuse a version whose protocol, skills or topology are IMPOSSIBLE | hook in place |
| run time | per-agent middleware | each process checks **its own** tools against the Tool's owner and precondition in the local protocol state; the owner check is also a deployment fact, because no process has another role's tools and each has its own identity (D1, no self-approval, holds even if a prompt asks RevenueAnalyst to approve: `approve_*` does not exist there); a 403 from a callee is the "no Foundry Agent Consumer on B" fact | middleware in place; see section 5 |

Note on the connection `target`: it contains `${FOUNDRY_PROJECT_ENDPOINT}`,
so `from-azd` records no host for it (`_public_host` drops unresolved
variables); the gate reads the raw `azure.yaml` and matches the target's
path suffix `/agents/<callee>/endpoint/protocols/a2a`, which is what names
the callee. The connection name `<caller>-to-<callee>` names both ends.

## 5. Per-agent monitors and the receive bridge

The monitor core evaluates a Tool's `requires` against the facts the **same
process's** tools added, and a callee (an `agent_tools` entry) is allowed
without changing state. In one process that is complete: `approve_audited`
adds `approved`, and `write_revenue_analysis` sees it. In six processes the
fact is added in `finance-tax-verifier` and reaches `finance-revenue-analyst`
only as the text `[Approval] Approved: ...`; without more, every tool with a
remote precondition (`analyze_expenses`, `audit_high_revenue`, `approve_*`,
`write_revenue_analysis`, `compose_report`) would be denied and the group
would stop at its first step.

`main.py` therefore adds the **receive half of the role's projection** as two
small middleware objects (`receive_bridge`): the agent middleware reads the
labels of the incoming request and the function middleware reads the labels
of each callee's reply, and both add the facts the label carries (the `adds`
of the sender's last tool before the message, from the pack) to the monitor's
state, under its lock. A label counts only through the channel the projection
allows it on: `[Approval]` counts for RevenueAnalyst only in the reply of its
`TaxVerifier` call, never in a request or in another callee's reply; a new
incoming request resets the facts, because one A2A request is one run of the
local protocol. The bridge trusts labels as the protocol trusts messages;
**who** may send them is the platform's check (Entra on every A2A endpoint,
Foundry Agent Consumer on the callee). What it does not do, and what skillc
should learn to do in the monitor itself, is bind the label to the A2A
caller's identity and derive the label-to-facts table from the pack instead
of the hand-written `MESSAGES` in `main.py`. The state file is
`$HOME/.skillc/<session>/state.json`, with the session from
`FOUNDRY_AGENT_SESSION_ID`.

## 6. Verify against azd

Fields and behaviours that the `azure.ai.*` azd extensions, not the core
`azure.yaml` schema, define, and that this example could not test offline:

* `azure.ai.connection` with `category: RemoteA2A` and `authType:
  AgenticIdentityToken`: the connection extension may spell these
  `--kind remote-a2a` / `--auth-type agentic-identity`, and may require
  `audience` as a separate flag rather than a key.
* `target: ${FOUNDRY_PROJECT_ENDPOINT}/agents/<callee>/endpoint/protocols/a2a`
  on a connection declared **before** the callee agent exists (the path is
  deterministic; provisioning order is azd's).
* Toolbox `a2a` entries: the toolbox extension may only create
  `type: a2a_preview` today; the connection key may be `project_connection_id`
  rather than `connection`; `a2a_version: "1.0"`.
* `agentEndpoint: {protocols: [responses, a2a], authorizationSchemes: [{type: Entra}]}`
  spelling, and whether `a2a` must also appear under `protocols:` with a
  version (`{protocol: a2a, version: "1.0"}`).
* The agent card path `.../endpoint/protocols/a2a/agentCard/v1.0` and whether
  the card's `supported_interfaces[0].url` equals the base path used by the
  code (`A2A_FETCH_CARD=1` prints the card at startup).
* The azd environment key `AGENT_<SERVICE>_INSTANCE_IDENTITY_PRINCIPAL_ID`
  (and the `azd ai agent show` label "Instance Identity Principal ID") used by
  `scripts/grant_a2a.sh`; whether a hosted agent is ARM-addressable at
  `<project id>/agents/<name>` for the per-agent scope.
* `codeConfiguration.dependencyResolution: remote_build`, `startupCommand`,
  `toolboxes: [{name}]` next to `uses` (as in the single example), and that
  six `azure.ai.agent` services may share one `project` folder.
* Whether an A2A-triggered run of a callee gets its own
  `FOUNDRY_AGENT_SESSION_ID` (and `$HOME`) per task, or shares one across
  calls: the receive bridge resets the facts per request either way, but the
  state file's location follows the session.
* `azure.ai.project.endpoint: ${FOUNDRY_PROJECT_ENDPOINT}` for an existing
  project, as in the single example.
