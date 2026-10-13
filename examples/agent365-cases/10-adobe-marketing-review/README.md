# Adobe Marketing Agent: campaign and audience analysis for a leadership review

**Source category:** Official worked scenario for a planned Agent 365 partner integration

## Verifiable real use case

Microsoft describes a marketing director preparing a leadership review by querying page views, orders and audience trends from Adobe Experience Platform, then analyzing campaign-journey fallout and conflicts inside Microsoft Copilot.

- The worked scenario queries top-page views, orders by category and audience-size trends.
- The director performs loyalty-campaign fallout analysis and reviews campaign conflicts.
- Microsoft describes query and dataset-access telemetry flowing through Agent 365 and Purview.
- The Adobe Marketing Agent integration is explicitly marked coming soon.

### Sources

- [Ecosystem partner agents available in Agent 365 - Adobe example scenarios](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#adobe) - Microsoft Learn; verified 2026-10-13 (Primary page and marketing-director worked scenario fetched and read directly.).

### Relationship to Agent 365

Direct but planned: the source explicitly links Adobe Marketing Agent to Agent 365 observability and Purview.

## Complete local case

**User intent:** Prepare a marketing leadership review from page views, orders, audience trends, journey fallout and campaign-conflict analysis.

**Actors:** Marketing director, Adobe Marketing Agent and IT observer; Agent abstracts the analysis workflow.

**Published outcome:** Published intended marketing-analysis workflow; no real campaign was queried and no conversion improvement is established.

**Modeled goal:** `leadership_review_prepared`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `query_campaign_metrics` | Query page views, orders and audience-size trends from Experience Platform. | `campaign_metrics_loaded` |
| `analyze_journey_fallout` | Analyze fallout in the campaign journey. | `journey_fallout_analyzed` |
| `review_campaign_conflicts` | Review conflicts relevant to campaign performance. | `campaign_conflicts_reviewed` |
| `prepare_leadership_review` | Prepare the resulting insights for the leadership review. | `leadership_review_prepared` |

### Explicit local test assumptions

- The workflow is serialized for the local model; the source does not publish a tool-call protocol.
- Independent approval before presenting the final review is an added local policy.
- A prepared review is an output milestone, not a proof of correct causal explanation for conversion changes.

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
   check verifies that the intent cannot manufacture `campaign_metrics_loaded`.
4. The runtime checks use `ApprovalGate` at `marketing.review.present`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `prepare_leadership_review` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `leadership_review_prepared` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `query_campaign_metrics` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |



## What does not work / remains unverified

- The integration is marked coming soon and no live Adobe datasets were accessed.
- SkillC cannot validate campaign metrics, causal analysis or the accuracy of the presentation.
- Actual Purview/Agent 365 telemetry ingestion remains unverified.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 10-adobe-marketing-review --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
