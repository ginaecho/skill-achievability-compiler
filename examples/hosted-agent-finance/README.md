# Quarterly Finance Report as a Foundry hosted agent

Six roles (Fetcher, RevenueAnalyst, ExpenseAnalyst, Writer, TaxVerifier,
TaxSpecialist) run as **one** Microsoft Foundry hosted agent built with the
Microsoft Agent Framework. skillc checks the project three times: offline
against the declared `azure.yaml`, at `azd deploy` through a `predeploy`
hook, and at run time as Agent Framework middleware.

```
examples/hosted-agent-finance/
  azure.yaml                 base: code_interpreter + web_search, no connections
  azure.search.yaml          + Azure AI Search connection `tax-rules-search`
  azure.isolated.yaml        + network isolation (AllowOnlyApprovedOutbound)
  skills/<Role>.md           one azure.ai.skill per role (the intent artifacts)
  skills-variants/Writer.email.md   the Writer variant that emails the report (IMPOSSIBLE on purpose)
  protocol/quarterly_finance_report.ce         the pack in Controlled English (the gate reads protocol/*.ce)
  protocol-variants/quarterly_finance_report.search.ce   the same pack with `lookup_tax_rules` via `search`
  protocol-variants/quarterly_finance_report.email.ce    the email variant of the pack
  src/finance-agent/main.py  Agent Framework coordinator + skillc middleware
```

## 1. The use case and where it comes from

The case is `experiments/cases/finance` of the session-typed-agents
repository: a Quarterly Finance Report pipeline with a value-dependent
branch (revenue above $50,000 is audited) and an explicit approval step. The
intent, in that repository's words:

> Produce a Quarterly Finance Report from fetched revenue and expense data.
> Revenue above $50,000 requires a TaxSpecialist audit. Standard revenue does
> not. TaxVerifier must explicitly approve every revenue analysis. Writer must
> receive both substantive analyses before delivering the final report.

### The global protocol (`protocols/v1.scr`, in MPST notation)

```
G =
Fetcher->RevenueAnalyst:RawRevenueData(Double).
Fetcher->ExpenseAnalyst:RawExpenseData(Double).
ExpenseAnalyst->RevenueAnalyst:ExpenseData(Double).
ExpenseAnalyst->Writer:ExpenseAnalysis(String).
RevenueAnalyst->TaxVerifier:{
  HighRevenueNotification(String).
    RevenueAnalyst->Writer:HighBranchNotification(String).
    RevenueAnalyst->TaxSpecialist:NotifyTaxSpecialist(String).
    TaxSpecialist->TaxVerifier:AuditReport(String).
    TaxVerifier->RevenueAnalyst:Approval(String).
    RevenueAnalyst->Writer:FinalRevenueAnalysis(String).
    Writer->Fetcher:GenerateReport(String). end,
  StandardRevenueNotification(String).
    RevenueAnalyst->Writer:StandardBranchNotification(String).
    RevenueAnalyst->TaxSpecialist:NotifyStandardRole(String).
    TaxVerifier->RevenueAnalyst:Approval(String).
    RevenueAnalyst->Writer:FinalRevenueAnalysis(String).
    Writer->Fetcher:GenerateReport(String). end
}
```

The skills in `skills/` name exactly these message labels, and the pack in
`protocol/quarterly_finance_report.ce` follows this order step by step, with
the role's tool call inserted before each message it produces.

### The policies (`protocols/v1.policy`) and how the pack encodes them

| id | kind | policy | encoding in the pack |
|---|---|---|---|
| S1 | sequence | `TaxVerifier -> RevenueAnalyst : Approval` precedes `RevenueAnalyst -> Writer : FinalRevenueAnalysis` | `write_revenue_analysis` **requires `approved`**; only `approve_audited` and `approve_standard` add `approved` |
| S2 | sequence | `FinalRevenueAnalysis` precedes `Writer -> Fetcher : GenerateReport` | the protocol order itself: `compose_report` requires `revenue_analysis`, `deliver_report` requires `report_written` |
| D1 | separation | no self-approval by the revenue analyst | the two approving tools are **owned only by `TaxVerifier`**; RevenueAnalyst owns no tool that adds `approved` |
| A1 | aggregate | at most one `Approval` per run | each branch sends `Approval` once; TaxVerifier's declared behaviour has exactly one `send Approval` per branch |

### The tool vocabulary (shared by the skills, the pack and `main.py`)

| tool | owner role | runtime tool it runs through | effect it adds |
|---|---|---|---|
| `fetch_financials` | Fetcher | `code_interpreter` (reads the quarter's CSV under `$HOME`) | `revenue_fetched`, `expenses_fetched` |
| `analyze_expenses` | ExpenseAnalyst | `code_interpreter` | `expense_analysis` |
| `classify_revenue` | RevenueAnalyst | `code_interpreter` (threshold $50,000) | `revenue_classified` |
| `lookup_tax_rules` | TaxSpecialist | `code_interpreter` (built-in rules in the deployed pack); `search` (the toolbox's Azure AI Search index) in `protocol-variants/quarterly_finance_report.search.ce` | `tax_rules_found` |
| `audit_high_revenue` | TaxSpecialist | `code_interpreter` | `audit_report` |
| `approve_audited` | TaxVerifier | `write` (records the approval under `$HOME/approvals`) | `approved` |
| `approve_standard` | TaxVerifier | `write` | `approved` |
| `write_revenue_analysis` | RevenueAnalyst | `write` | `revenue_analysis` (requires `approved`) |
| `compose_report` | Writer | `code_interpreter` | `report_written` |
| `deliver_report` | Writer | `write` (to `$HOME/files`) | `report_delivered` |
| `email_report` (variant only) | Writer | an email MCP tool that needs an email connection | `report_emailed` |

## 2. How the hosted agent is built

* **One hosted agent, six role agents as tools.** `src/finance-agent/main.py`
  creates a coordinator `Agent` whose tools are the six role agents, each an
  `Agent` with its own instructions (the role's `skills/<Role>.md`) and its
  own tools from the table above. The role tools run through the project's
  toolbox (`code_interpreter`, `azure_ai_search`) or write under `$HOME`.
* **Agent Framework, Responses protocol.** `FoundryChatClient` against the
  project endpoint and the `gpt-5.4` deployment; `ResponsesHostServer(agent).run()`
  serves `protocols: [{protocol: responses, version: 2.0.0}]` on port 8088
  locally.
* **skillc middleware.** The coordinator and the role agents are created with
  `middleware=[SkillcMonitor(...)]` (function middleware). Every tool call is
  checked against the pack: a call whose preconditions do not hold
  (`write_revenue_analysis` before `approved`) or whose owner is wrong
  (anyone but TaxVerifier approving) is denied by setting `context.result`
  and not calling `call_next()`; the model sees the denial as a normal tool
  result and does not retry (spike fact F2 in `docs/HOSTED_AGENT.md`).
* **Declared in `azure.yaml`.** The project (existing, reached by
  `FOUNDRY_PROJECT_ENDPOINT`), the toolbox `finance-tools`, one
  `azure.ai.skill` per role, and the `azure.ai.agent` `finance-report-agent`
  (`kind: hosted`, code deploy mode: `codeConfiguration` with
  `runtime: python_3_13`, `entryPoint: main.py`, remote build; no Dockerfile).
  The `agentCard` lists one skill per role.

## 3. How it is deployed

`azd ai agent init` is not needed: the project is hand-written. The project
already exists and already has the `gpt-5.4` deployment, so `azure.yaml`
declares no `deployments`.

```console
$ azd env set FOUNDRY_PROJECT_ENDPOINT https://<account>.services.ai.azure.com/api/projects/<project>
$ azd provision                      # toolbox, skills, connections (search variant) on the existing project
$ azd ai agent run                   # the real code against the real project, from the laptop (port 8088)
$ azd ai agent invoke --local "Produce the Q3 report"
$ azd deploy                         # runs the predeploy hook below, then creates one immutable agent version
$ azd ai agent invoke "Produce the Q3 report"
$ azd ai agent monitor --follow      # skillc verdicts in the trace
```

The gate is the `predeploy` hook in every `azure.yaml` here:

```yaml
hooks:
  predeploy:
    shell: sh
    run: skillc gate . --declared azure.yaml
```

`azd deploy` is the only moment an agent version is created, so this is where
an IMPOSSIBLE intent is refused before anything is uploaded.

To try the two variants, copy the variant over `azure.yaml` (or pass it, if
your `azd` version reads an alternate file name; **verify against azd**):
`azure.search.yaml` adds the `tax-rules-search` connection and the
`azure_ai_search` tool; `azure.isolated.yaml` adds `network.isolationMode:
AllowOnlyApprovedOutbound` with a private-endpoint subnet
(`azd env set VNET_RESOURCE_ID ...`).

## 4. The skillc checks

Run from this directory with the repository's virtual environment
(`../../.venv/Scripts/python.exe -m skillc.cli ...`, or `skillc ...` once
installed). Verdicts marked "run 2026-10-07" were produced while writing this
example; the others are to be filled by the run.

| step | command | expected | verdict |
|---|---|---|---|
| declared environment, base | `skillc env from-azd azure.yaml -o .skillc/env/declared.json` | 6 nodes, 2 unknowns, no `search` tool | run 2026-10-07: see summaries below |
| declared environment, search | `skillc env from-azd azure.search.yaml -o .skillc/env/declared.search.json` | 8 nodes: + `connection/tax-rules-search`, + `toolbox/finance-tools/azure_ai_search/tax-rules-search` | run 2026-10-07: see summaries below |
| declared environment, isolated | `skillc env from-azd azure.isolated.yaml -o .skillc/env/declared.isolated.json` | 6 nodes, 3 unknowns; egress "network-isolated project; public hosts unknown until probed from inside" | run 2026-10-07: see summaries below |
| pure pack: realizability and the branch | `skillc check protocol/quarterly_finance_report.ce` | ACHIEVABLE; witness through the `HighRevenueNotification` branch; TaxVerifier's behaviour conforms, the five other roles assumed conformant | run 2026-10-07: **ACHIEVABLE** (`-v` witness: `fetch_financials -> RawRevenueData -> ... -> approve_audited -> Approval -> write_revenue_analysis -> FinalRevenueAnalysis -> compose_report -> deliver_report -> GenerateReport`) |
| runtime-bound: bind the monitor | `skillc monitor init --runtime foundry-hosted` | writes `.skillc/monitor.json` with the `foundry-hosted` runtime manifest | run 2026-10-07: written |
| runtime-bound: which tools are withdrawn | `skillc monitor plan protocol/quarterly_finance_report.ce` | ACHIEVABLE via `code_interpreter`, `write`; nothing withdrawn by the runtime manifest (whether the *project* exposes a tool is the gate's business, see below) | run 2026-10-07 (then still `via search`): **ACHIEVABLE**, `withdrawn: {}` |
| email variant | `skillc monitor plan protocol-variants/quarterly_finance_report.email.ce` | **IMPOSSIBLE**: `email_report` needs `email_account`, which no connection declares | run 2026-10-07: **IMPOSSIBLE**, `action: deny`, `reason: BLOCKED_GUARD`, `blocked: {email_report: [email_account]}`, exit 1 |
| intent of one role | `skillc intent skills/TaxSpecialist.md` | the role's needs from its runtime | run 2026-10-07: `tax-specialist` needs `deliverable` (the natural-language front-end extracts no tool or connection need from these skills yet) |
| reach, per variant | `skillc reach skills/TaxSpecialist.md --env .skillc/env/declared.json` (and `.search`, `.isolated`) | base: `lookup_tax_rules` has no `search` tool to run through; search: achievable under the assumption the toolbox really exposes `azure_ai_search`; isolated: egress unknown | run 2026-10-07: `1/1 conditions achievable` in all three (only `deliverable` is extracted today, so `reach` does not yet separate the variants; the pack-level checks above do) |
| the deploy gate, base | `skillc gate . --declared azure.yaml` | **ACHIEVABLE**, exit 0: the runtime keeps `code_interpreter`, `web_search`, `web_fetch`, `read`, `write` and withdraws `search`, `mcp`, `openapi`, `a2a` (not declared); the deployed pack uses only `code_interpreter` and `write`; six skills ACHIEVABLE; single agent, so messages are in-process | run 2026-10-08: **ACHIEVABLE**, exit 0 |
| the deploy gate, search | `skillc gate . --declared azure.search.yaml` | **ACHIEVABLE**, exit 0: `search` is kept (`azure_ai_search` in the toolbox) | run 2026-10-08: **ACHIEVABLE**, exit 0 |
| the deploy gate, isolated | `skillc gate . --declared azure.isolated.yaml` | **ACHIEVABLE**, exit 0: `web_fetch` is kept only as an assumption (egress unknown), and nothing in the project uses it; a pack `via web_fetch` would make the gate UNKNOWN, exit 3 | run 2026-10-08: **ACHIEVABLE**, exit 0 |
| flip the impossible pack in: email | `cp protocol-variants/quarterly_finance_report.email.ce protocol/ && skillc gate . --declared azure.yaml` | **IMPOSSIBLE**, exit 1: `email_report` is blocked, the runtime does not grant `email_account`; `azd deploy` is refused | run 2026-10-08: **IMPOSSIBLE**, exit 1 |
| flip the impossible pack in: search under base | `cp protocol-variants/quarterly_finance_report.search.ce protocol/ && skillc gate . --declared azure.yaml` | **IMPOSSIBLE**, exit 1: `lookup_tax_rules` cannot run, `search` is not declared; fix "add `azure_ai_search` to a toolbox the agent uses"; the same command with `--declared azure.search.yaml` is ACHIEVABLE | run 2026-10-08: **IMPOSSIBLE**, exit 1 |
| flip the impossible skill in | `cp skills-variants/Writer.email.md skills/ && skillc gate . --declared azure.yaml` | the skill is picked up as a seventh artifact; its prose names no tool or connection the front-end can refute, so it stays ACHIEVABLE; a skill whose frontmatter says `tools: [azure_ai_search]` is **IMPOSSIBLE** under base, exit 1 | run 2026-10-08: as expected |

Note on the variants folders: `protocol-variants/` and `skills-variants/` are
the "flip the impossible skill in" material. The gate reads every
`protocol/*.ce` and every `skills/*.md` beside `azure.yaml` (through
`intent_artifacts()`), and nothing under the variants folders. Copy a variant
into `protocol/` or `skills/` and `azd deploy` is refused by the predeploy
hook (exit 1); remove it and the deploy goes through again.

### `skillc env from-azd` summaries (run 2026-10-07)

All three files load (`exit 0`, `schema: skillc.env/1`), and each prints the
same intent artifacts to stderr: `skills/Fetcher.md`, `RevenueAnalyst.md`,
`ExpenseAnalyst.md`, `Writer.md`, `TaxVerifier.md`, `TaxSpecialist.md`
(`Writer.email.md` only while it is copied into `skills/`, see the note above).

| file | nodes | by kind | unknowns |
|---|---|---|---|
| `azure.yaml` | 6 | mcp_server 1 (`toolbox/finance-tools`), principal 1 (`principal/agent/finance-report-agent`), scope 1, service 1 (`egress/public`), tool 2 (`code_interpreter`, `web_search`) | 2: `value:FOUNDRY_PROJECT_ENDPOINT` (unresolved azd variable); `egress` ("declared AllowInternetOutbound; measure from inside the sandbox") |
| `azure.search.yaml` | 8 | as base + service `connection/tax-rules-search` (CognitiveSearch, AAD, host `tax-rules.search.windows.net`), tool `toolbox/finance-tools/azure_ai_search/tax-rules-search` | 2: the same two |
| `azure.isolated.yaml` | 6 | as base; `egress/public` has `mode: AllowOnlyApprovedOutbound`, `isolated: true` | 3: `value:FOUNDRY_PROJECT_ENDPOINT`; `value:VNET_RESOURCE_ID`; `egress` ("network-isolated project; public hosts unknown until probed from inside") |

Every node carries `declared: true`: a declared fact is an assumption until
`skillc env probe --foundry` (WP5) observes it.

## 5. Verify against azd

These `azure.yaml` fields are handled by the `azure.ai.*` azd extensions, not
by the core `azure.yaml` JSON schema (which lists the `azure.ai.*` hosts only
as examples), so their exact spelling must be verified against the installed
extension versions before `azd provision`:

* `azure.ai.project.endpoint: ${FOUNDRY_PROJECT_ENDPOINT}` as the way to bind
  an existing project (versus a resource id or an `existing:` block).
* `codeConfiguration.dependencyResolution: remote_build` and
  `startupCommand: python main.py` on the hosted agent (the foundry-samples
  files declare only `runtime` and `entryPoint`).
* `toolboxes: [{name: finance-tools}]` next to `uses` (skillc reads both).
* `agentCard.description` and `agentCard.skills[].{id,name,description}`.
* `network.peSubnet: {vnet, name}` on the project (skillc's fixture uses
  `agentSubnet: <resource id>`; skillc reads `isolationMode` for the egress
  mode either way, and it treats `peSubnet` as part of the isolated mode only
  because `isolationMode` is not `AllowInternetOutbound`).
* `authType: AAD` on the CognitiveSearch connection without `credentials`.
* whether `azd` reads `azure.search.yaml` / `azure.isolated.yaml` by name, or
  the variant must be copied over `azure.yaml`.

## 6. Deploy log (2026-10-07, project `firstProject`, Germany West Central)

The first live deployment of this example, done before the skillc adapter
existed, so the agent runs unmonitored and the predeploy hook is the pure
protocol check (`skillc check protocol/quarterly_finance_report.ce`, which
also stages `skills/` and `data/` into `src/finance-agent/`, the only folder
that is uploaded).

```console
$ azd env new finance
$ azd env set FOUNDRY_PROJECT_ENDPOINT https://<account>.services.ai.azure.com/api/projects/<project>
$ azd env set AZURE_AI_PROJECT_ID /subscriptions/<sub>/resourceGroups/<rg>/providers/Microsoft.CognitiveServices/accounts/<account>/projects/<project>
$ azd env set AZURE_SUBSCRIPTION_ID <sub>; azd env set AZURE_LOCATION <region>; azd env set AZURE_RESOURCE_GROUP <rg>
$ azd provision --no-prompt        # resolves the existing project, creates nothing
$ azd deploy --no-prompt           # hook, toolbox, six skills, agent version 1 (1 min 24 s)
$ azd ai agent show finance-report-agent
$ azd ai agent invoke finance-report-agent "Produce the quarterly finance report for 2026-Q3. ..."
```

Result: `finance-report-agent:1` active, with its own Entra agent identity, a
playground URL and a Responses endpoint. The Q3 invocation took the **high**
branch (revenue 72,000 > 50,000), TaxVerifier answered "Approved: high-revenue
audit reviewed and recorded", and the report landed at
`/home/session/files/quarterly_report.md` in the sandbox; 62 s end to end,
8.5 s of it cold-start platform latency.

The Q2 invocation (revenue 41,000) took the **standard** branch, but
TaxVerifier answered "Rejected: missing the revenue total required to confirm
the standard branch threshold" and the coordinator stopped without a report
(30 s, warm). That is correct behaviour by the verifier and a data-flow defect
in the coordinator: a role agent exposed through `as_tool()` receives one
`task` string, and the coordinator did not include the revenue total in it.
The fix is in the coordinator's instructions (always pass the figures the
callee's tools need), and it is the kind of run-time fact the monitor will
observe once attached: a tool result starting with `Rejected:` on the
approval step.

Three things the documentation did not say, each of which stopped a deploy:

1. **`AZURE_AI_PROJECT_ID` is required** when the project is existing: the agent
   extension does not derive the ARM resource id from `FOUNDRY_PROJECT_ENDPOINT`.
   From Git Bash, set it with `MSYS_NO_PATHCONV=1` or the leading `/` becomes a
   Windows path.
2. **azd must hold its own sign-in.** In `useAzCliAuth` mode every token goes
   through the Azure CLI (16 s on this machine) and the Foundry extensions'
   credential gives up at 10 s (`AzureDeveloperCLICredential: exit status 1`).
   `azd config set auth.useAzCliAuth false` then `azd auth login` (the browser
   flow; a device-code login is refused by a managed-device Conditional Access
   rule because it carries no device identity).
3. **Stray system variables win.** The skills extension read
   `AZURE_SUBSCRIPTION_ID`, `AZURE_TENANT_ID` and `AZURE_CLIENT_ID` from the
   machine environment (left by another project) before the azd environment,
   and failed on a subscription this user cannot see. Export the right values
   (and unset the client id) in the shell that runs `azd deploy`.

These belong in `skillc env probe --self` and the gate's preflight: a declared
project with no resource id, a credential that cannot answer in time, and a
principal variable that names a different tenant are all facts the environment
graph can hold.

### The gate refusing a deploy (2026-10-08)

With `protocol-variants/quarterly_finance_report.email.ce` copied into
`protocol/`, `azd deploy finance-report-agent` stopped in the predeploy hook
before packaging anything:

```text
ERROR: failed running pre hooks: 'predeploy' hook failed with exit code: '1'
pack quarterly_finance_report.email.ce: IMPOSSIBLE MISSING_CAPABILITY: Tool `email_report`
  needs `email_account`, which the runtime does not grant; Tool `email_report` cannot run
  here: `mcp` is not declared in azure.yaml
    fix: declare in azure.yaml a connection that provides `email_account` for
         `email_report`, or make the step skippable
gate: IMPOSSIBLE
```

The live agent stayed at version 8. The log is
`runs/20261007_hosted_agent_deploy/azd-deploy-refused-by-gate.log`.
