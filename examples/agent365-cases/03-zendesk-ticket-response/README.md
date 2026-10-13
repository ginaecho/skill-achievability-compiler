# Zendesk: customer ticket management and response from Teams

**Source category:** Documented Agent 365 partner workflow

## Verifiable real use case

Microsoft describes service engineers viewing and managing a customer's Zendesk tickets inside Teams, then communicating with customers and internal teams without switching applications.

- The integration surfaces all tickets for a customer in context within Teams.
- Service engineers can communicate with customers and internal teams from Microsoft 365.
- Agent activity is described as visible through Agent 365 observability.

### Sources

- [Ecosystem partner agents available in Agent 365 - Zendesk](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#zendesk) - Microsoft Learn; verified 2026-10-13 (Primary page and Zendesk section fetched and read directly.).

### Relationship to Agent 365

Direct: the Zendesk integration is explicitly listed under Agent 365; no specific customer deployment is asserted.

## Complete local case

**User intent:** Find a customer's support tickets in Teams, review the relevant ticket context and send an appropriate response.

**Actors:** Service engineer, Zendesk agent, customer and internal support team; one Agent role abstracts the tool workflow.

**Published outcome:** Documented in-context ticket management and communication, not a verified resolution rate.

**Modeled goal:** `ticket_response_sent`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `find_customer_tickets` | Find the customer's Zendesk tickets in context. | `tickets_found` |
| `review_ticket_context` | Review and manage the relevant ticket context. | `ticket_context_reviewed` |
| `prepare_ticket_response` | Prepare a response using that ticket context. | `ticket_response_prepared` |
| `send_ticket_response` | Communicate the response to the selected customer or internal team. | `ticket_response_sent` |

### Explicit local test assumptions

- Preparing a response is an explicit modeling step within the source's communication workflow; no Zendesk internal implementation is claimed.
- A local test contract distinguishes a sent response from one merely queued.
- Independent response approval and exact destination allowlisting are local test controls; the source does not mandate them.

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
   check verifies that the intent cannot manufacture `tickets_found`.
4. The runtime checks use `ApprovalGate` at `support.reply.send`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `send_ticket_response` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `ticket_response_sent` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `find_customer_tickets` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |



## What does not work / remains unverified

- The model cannot determine whether the reply actually solves the customer's problem.
- Customer identity, ticket access and tenant entitlement require real authenticated integrations.
- Refunds and customer-credit issuance are not modeled because the source does not describe those actions.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 03-zendesk-ticket-response --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
