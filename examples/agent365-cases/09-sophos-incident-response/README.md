# Sophos: security-alert triage and response from Teams

**Source category:** Documented Agent 365 partner workflow

## Verifiable real use case

Microsoft describes Sophos security alerts, triage and response actions in Microsoft 365, allowing security teams to work from Teams rather than a separate console. The model uses a generic documented response operation, not an invented endpoint-isolation command.

- Sophos alerts and threat notifications can surface in Teams.
- Security teams can triage and respond to incidents from Microsoft 365.
- Agent activity is described as tracked in the admin-center observability dashboard.

### Sources

- [Ecosystem partner agents available in Agent 365 - Sophos](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#sophos) - Microsoft Learn; verified 2026-10-13 (Primary page and Sophos section fetched and read directly.).

### Relationship to Agent 365

Direct: Microsoft explicitly names the Sophos Agent 365 integration.

## Complete local case

**User intent:** Receive a security alert in Teams, triage the incident and carry out an authorized response.

**Actors:** Security analyst, Sophos agent and incident target; one abstract Agent role.

**Published outcome:** Documented in-Teams incident-response capability, not measured prevention or remediation effectiveness.

**Modeled goal:** `incident_response_executed`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `receive_security_alert` | Receive the Sophos security alert or threat notification. | `security_alert_received` |
| `triage_security_incident` | Triage the incident using its alert context. | `security_incident_triaged` |
| `execute_incident_response` | Execute an authorized incident response from the Microsoft 365 workflow. | `incident_response_executed` |

### Explicit local test assumptions

- The response capability is intentionally abstract because the source does not enumerate concrete response commands.
- Independent approval of the exact response content and target is a local policy, not a documented Sophos requirement.
- All alert and target data are synthetic; the transport never contacts an endpoint.

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
   check verifies that the intent cannot manufacture `security_alert_received`.
4. The runtime checks use `ApprovalGate` at `security.incident.respond`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `execute_incident_response` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `incident_response_executed` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `receive_security_alert` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |



## What does not work / remains unverified

- The checker cannot determine whether an alert is a real threat or whether the selected response is effective.
- Authorization for a specific destructive response must be supplied by a real policy and tool adapter.
- No live incident handling, endpoint isolation or remediation was performed.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 09-sophos-incident-response --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
