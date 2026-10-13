# Gloat: internal career and project recommendations in Teams

**Source category:** Documented Agent 365 partner workflow

## Verifiable real use case

Microsoft describes Gloat's talent marketplace surfacing personalized career and project opportunities in Teams. The case models recommendations and exploration, not job applications, hiring decisions or transfers absent from the source.

- Gloat connects employees with internal opportunities, projects and career paths.
- The Agent 365 integration surfaces personalized recommendations in Teams.
- Employees can explore internal opportunities without leaving Microsoft 365.

### Sources

- [Ecosystem partner agents available in Agent 365 - Gloat](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#gloat) - Microsoft Learn; verified 2026-10-13 (Primary page and Gloat section fetched and read directly.).

### Relationship to Agent 365

Direct: the Gloat Agent 365 integration is named explicitly.

## Complete local case

**User intent:** Find relevant internal career and project opportunities and surface recommendations to an employee in Teams.

**Actors:** Employee and Gloat talent agent; the model contains no hiring authority.

**Published outcome:** Documented recommendation and exploration capabilities, not a measured hiring or mobility outcome.

**Modeled goal:** `recommendations_surfaced`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `access_internal_opportunities` | Access internal career and project opportunities. | `opportunities_available` |
| `prepare_personalized_recommendations` | Prepare personalized opportunity recommendations. | `recommendations_prepared` |
| `surface_employee_recommendations` | Surface those recommendations in the employee's Teams workflow. | `recommendations_surfaced` |

### Explicit local test assumptions

- The state vocabulary models availability and presentation, not fairness or fitness of a recommendation.
- The runtime test permits output only to the synthetic employee destination and adds independent approval as a test policy.
- The source does not supply profile authorization rules or a manager-notification requirement.

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
   check verifies that the intent cannot manufacture `opportunities_available`.
4. The runtime checks use `ApprovalGate` at `teams.recommendation.present`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `surface_employee_recommendations` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `recommendations_surfaced` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `access_internal_opportunities` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |



## What does not work / remains unverified

- SkillC does not evaluate recommendation fairness, discrimination or career suitability.
- Employee-profile permissions and consent are not observed in this offline model.
- Submitting applications and hiring decisions are deliberately out of scope.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 05-gloat-opportunity-recommendations --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
