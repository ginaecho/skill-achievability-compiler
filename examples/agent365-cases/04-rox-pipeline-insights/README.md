# Rox: sales deal health and revenue insights in Teams

**Source category:** Documented Agent 365 partner workflow

## Verifiable real use case

Microsoft documents Rox revenue intelligence inside Teams, including deal health, pipeline status, forecasts and actions on recommendations. This model stays within retrieving and presenting those insights rather than inventing discount or CRM-write operations.

- Rox revenue data is surfaced in Microsoft Teams.
- The documented data includes deal health, pipeline status and revenue forecasts.
- Rox agent activity is tracked through the Microsoft 365 admin-center observability dashboard.

### Sources

- [Ecosystem partner agents available in Agent 365 - Rox](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#rox) - Microsoft Learn; verified 2026-10-13 (Primary page and Rox section fetched and read directly.).

### Relationship to Agent 365

Direct: Microsoft explicitly describes the Rox Agent 365 integration.

## Complete local case

**User intent:** Retrieve deal health and pipeline forecasts and present relevant revenue insights to the sales team in Teams.

**Actors:** Sales representative or manager and Rox agent; locally abstracted as Agent.

**Published outcome:** Documented access to pipeline insights in Teams; forecast accuracy and sales outcomes are not established by these tests.

**Modeled goal:** `sales_insight_presented`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `read_deal_health` | Access the relevant deal-health data. | `deal_health_loaded` |
| `read_pipeline_forecast` | Access pipeline status and revenue forecasts. | `pipeline_forecast_loaded` |
| `prepare_revenue_insight` | Prepare the relevant revenue insight or recommendation. | `revenue_insight_ready` |
| `present_sales_insight` | Present the insight in the sales team's Teams workflow. | `sales_insight_presented` |

### Explicit local test assumptions

- The sequential dependency between datasets and presentation is a local simplified contract.
- The runtime test adds review of the exact forecast summary before publishing it to an allowlisted conversation.
- No CRM discount change, price approval or write-back permission is claimed from this source.

The checked-in `intent.md` describes requirements only. `intent.json` is a
human-authored formalization of those requirements, with no tool-effect definitions.
`environment.json` independently declares test grants, contracts and initial facts.
The source does not publish these formal contracts or prove its live grants.
Runtime fixture IDs, content, reviewer and destinations are fictional local test
values, not customer records. Independent review in the runtime tests is an added
local policy, not a claim about the organization's deployment.

## How SkillC works here

1. `bind_environment` binds named requirements to the declared grants and substitutes
   the environment's tool contracts and initial facts.
2. The trusted checker evaluates capability availability, the declared protocol,
   preconditions and goal reachability. No LLM extracts or judges this case.
3. `checks.json` varies grants, effects and protocol steps. The forged-initial-evidence
   check verifies that the intent cannot manufacture `deal_health_loaded`.
4. The runtime checks use `ApprovalGate` at `teams.insight.post`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `present_sales_insight` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `sales_insight_presented` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `read_deal_health` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |



## What does not work / remains unverified

- Structural admissibility does not prove forecast accuracy or recommendation usefulness.
- Actual CRM row-level access and data freshness are not discovered.
- Any concrete sales write-back action would need its own documented tool contract and policy.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 04-rox-pipeline-insights --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
