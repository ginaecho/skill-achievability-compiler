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
  skills/Writer.email.md     the Writer variant that emails the report (IMPOSSIBLE on purpose)
  protocol/quarterly_finance_report.ce         the pack in Controlled English
  protocol/quarterly_finance_report.email.ce   the email variant of the pack
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
| `lookup_tax_rules` | TaxSpecialist | `search` (Azure AI Search index of tax rules, through the toolbox) | `tax_rules_found` |
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
| runtime-bound: which tools are withdrawn | `skillc monitor plan protocol/quarterly_finance_report.ce` | ACHIEVABLE via `code_interpreter`, `search`, `write`; nothing withdrawn by the runtime manifest (the manifest grants `search`; whether the *project* exposes it is the declared environment's business, see below) | run 2026-10-07: **ACHIEVABLE**, `via: [code_interpreter, search, write]`, `withdrawn: {}` |
| email variant | `skillc monitor plan protocol/quarterly_finance_report.email.ce` | **IMPOSSIBLE**: `email_report` needs `email_account`, which no connection declares | run 2026-10-07: **IMPOSSIBLE**, `action: deny`, `reason: BLOCKED_GUARD`, `blocked: {email_report: [email_account]}`, exit 1 |
| intent of one role | `skillc intent skills/TaxSpecialist.md` | the role's needs from its runtime | run 2026-10-07: `tax-specialist` needs `deliverable` (the natural-language front-end extracts no tool or connection need from these skills yet) |
| reach, per variant | `skillc reach skills/TaxSpecialist.md --env .skillc/env/declared.json` (and `.search`, `.isolated`) | base: `lookup_tax_rules` has no `search` tool to run through; search: achievable under the assumption the toolbox really exposes `azure_ai_search`; isolated: egress unknown | run 2026-10-07: `1/1 conditions achievable` in all three (only `deliverable` is extracted today, so `reach` does not yet separate the variants; the pack-level checks above do) |
| the deploy gate (predeploy hook) | `skillc gate . --declared azure.yaml` | exit 0 with the six role skills; non-zero once `skills/Writer.email.md` is the Writer | to be filled by the run: `gate` lands in S2 of the implementation plan; check `skillc --help` for it (absent in the build used here, 2026-10-07) |

Note on the gate and `skills/Writer.email.md`: `intent_artifacts()` lists
every `skills/*.md` beside `azure.yaml`, so the email variant is picked up by
the gate as a seventh artifact. That is the "flip the impossible skill in"
step of WP4; move it out of `skills/` (or point the `writer` service at it and
remove `Writer.md`) to switch between the achievable and the refused deploy.

### `skillc env from-azd` summaries (run 2026-10-07)

All three files load (`exit 0`, `schema: skillc.env/1`), and each prints the
same intent artifacts to stderr: `skills/Fetcher.md`, `RevenueAnalyst.md`,
`ExpenseAnalyst.md`, `Writer.md`, `TaxVerifier.md`, `TaxSpecialist.md`, plus
`Writer.email.md` (see the note above).

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
