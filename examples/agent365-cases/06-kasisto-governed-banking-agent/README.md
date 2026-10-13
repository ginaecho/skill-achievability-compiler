# Kasisto KAI: governed financial-services agents in Teams

**Source category:** Documented Agent 365 partner agent-factory workflow

## Verifiable real use case

Microsoft describes KAI as a financial-services agent factory whose created agents receive Entra Agent IDs, participate in Teams conversations and can be managed and monitored through Agent 365. The model uses this documented provisioning-to-collaboration workflow, not invented banking transactions.

- KAI builds line-of-business agents for banks and credit unions.
- The integration automatically provisions a Microsoft Entra Agent ID for each KAI-built agent.
- KAI agents participate in Teams one-to-one and group conversations and are managed through the admin center.

### Sources

- [Ecosystem partner agents available in Agent 365 - Kasisto](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#kasisto) - Microsoft Learn; verified 2026-10-13 (Primary page and Kasisto section fetched and read directly.).

### Relationship to Agent 365

Direct: KAI-created agents are explicitly described as governed Agent 365 agents with Entra Agent IDs.

## Complete local case

**User intent:** Create a financial-services agent, provision its governed identity and enable its participation in an authorized Teams conversation.

**Actors:** Bank platform operator, KAI agent factory and financial-services agent; simplified Factory role.

**Published outcome:** Documented governed provisioning and Teams collaboration; no specific bank or transaction outcome is asserted.

**Modeled goal:** `teams_collaboration_enabled`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `build_kai_agent` | Build the financial-services line-of-business agent on KAI. | `kai_agent_built` |
| `provision_agent_identity` | Provision its Microsoft Entra Agent ID through the integration. | `agent_identity_provisioned` |
| `enable_teams_collaboration` | Enable the governed agent to participate in Teams conversations. | `teams_collaboration_enabled` |

### Explicit local test assumptions

- Provisioning is represented by an explicit capability for testing although the product describes it as automatic.
- The local runtime gate reviews a specific conversation-enablement operation and destination.
- An identity-provisioned predicate does not imply permission to read accounts or move funds.

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
   check verifies that the intent cannot manufacture `kai_agent_built`.
4. The runtime checks use `ApprovalGate` at `agent.teams.enable`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `enable_teams_collaboration` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `teams_collaboration_enabled` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `build_kai_agent` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |



## What does not work / remains unverified

- The source does not specify a concrete account-disclosure, loan or funds-transfer workflow; none is claimed here.
- SkillC cannot provision or authenticate Entra Agent IDs in this offline case.
- Compliance with financial regulation and effective account permissions is outside the formal model.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 06-kasisto-governed-banking-agent --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
