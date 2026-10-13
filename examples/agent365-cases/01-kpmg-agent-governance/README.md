# KPMG: enterprise agent governance and lifecycle management

**Source category:** Named-customer adoption announcement, not a measured production workflow

## Verifiable real use case

KPMG and Microsoft announced Agent 365 adoption to govern agent deployment, management, monitoring and updates across KPMG, alongside Copilot expansion. This case models those stated lifecycle operations, not an invented audit-client transaction.

- The Microsoft press release explicitly names KPMG's adoption of Agent 365.
- The stated use is governance of agent deployment, management, monitoring and updates.
- The announcement connects this work with KPMG's Trusted AI framework and Workbench platform.

### Sources

- [KPMG and Microsoft scale trusted, enterprise AI agents globally through deployment of Agent 365 and Copilot](https://news.microsoft.com/source/2026/06/09/kpmg-and-microsoft-scale-trusted-enterprise-ai-agents-globally-through-deployment-of-agent-365-and-copilot/) - Microsoft Source; verified 2026-10-13 (Primary page fetched and read by the research agent; reported HTTP 200.).

### Relationship to Agent 365

Direct: the announcement explicitly names Microsoft Agent 365. It does not establish that every member firm's rollout is complete.

## Complete local case

**User intent:** Bring an enterprise agent into managed deployment, monitor its activity and apply a governed lifecycle update.

**Actors:** Enterprise governance administrators and the managed agent; local model role GovernanceAgent abstracts their workflow.

**Published outcome:** An announced governed agent operating model; no independently observed completion rate or security effectiveness is claimed here.

**Modeled goal:** `managed_update_applied`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `prepare_managed_agent` | Prepare an agent for managed enterprise deployment. | `agent_prepared` |
| `deploy_managed_agent` | Deploy the prepared agent under enterprise management. | `agent_deployed` |
| `monitor_agent_activity` | Monitor the deployed agent's activity. | `activity_observed` |
| `update_managed_agent` | Apply a managed lifecycle update to the agent. | `managed_update_applied` |

### Explicit local test assumptions

- The four named capabilities and their sequential effects are local abstractions, not KPMG API names or a published KPMG execution protocol.
- The declared environment grants each modeled lifecycle operation; actual tenant grants and rollout state are unknown.
- Independent approval of the exact lifecycle update is an added local runtime test policy, not a stated KPMG approval procedure.

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
   check verifies that the intent cannot manufacture `agent_prepared`.
4. The runtime checks use `ApprovalGate` at `agent.lifecycle.update`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `update_managed_agent` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `managed_update_applied` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `prepare_managed_agent` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |



## What does not work / remains unverified

- SkillC cannot establish rollout completion or query KPMG's private registry.
- The checker does not validate the meaning or completeness of KPMG governance controls.
- Actual Entra permissions, authenticated approvers and lifecycle API execution need a trusted host adapter.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 01-kpmg-agent-governance --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
