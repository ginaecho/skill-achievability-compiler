# Genspark: approved research and Word-document collaboration in Teams

**Source category:** Documented Agent 365 partner workflow

## Verifiable real use case

Microsoft documents Genspark in Teams conversations for research, summarization and task execution, with Word-document collaboration and user approval or rejection of actions. The source also says Genspark calls sub-agents internally.

- Genspark can participate in Teams one-to-one and group conversations for research and task execution.
- Users can create and collaborate on Word documents from a Genspark conversation.
- The integration supports human approval or rejection before proceeding and tracks activity through Agent 365.
- Genspark can call one or more sub-agents; the source does not establish unbounded dynamic spawning.

### Sources

- [Ecosystem partner agents available in Agent 365 - Genspark](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#genspark) - Microsoft Learn; verified 2026-10-13 (Primary page and Genspark section fetched and read directly.).

### Relationship to Agent 365

Direct: Microsoft lists the Genspark Agent 365 integration. Its AI teammate category has a Frontier-program availability caveat.

## Complete local case

**User intent:** Research a topic requested in Teams and create a collaborative Word document only after the proposed action is approved.

**Actors:** Teams user, Genspark agent and approving user; simplified local Agent and Reviewer roles.

**Published outcome:** Documented research, Word collaboration and human-in-the-loop capabilities, not independently observed customer productivity measurements.

**Modeled goal:** `word_document_created`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `research_topic` | Research the topic requested in the Teams conversation. | `research_ready` |
| `prepare_document_action` | Prepare the proposed Word-document action from the research. | `document_action_ready` |
| `approve_document_action` | Obtain approval before executing the proposed action. | `document_action_approved` |
| `create_word_document` | Create the approved document for collaboration. | `word_document_created` |

### Explicit local test assumptions

- The role handoffs and Boolean approval predicate formalize the published human-in-the-loop behavior; no exact Genspark protocol is asserted.
- The local declared environment assumes the necessary Teams and Word capabilities and entitlement.
- A separate stress variant introduces unbounded dynamic spawning to exercise UNKNOWN; this is not claimed to be Genspark's actual topology.

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
   check verifies that the intent cannot manufacture `research_ready`.
4. The runtime checks use `ApprovalGate` at `word.document.create`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `create_word_document` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `word_document_created` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `research_topic` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |

- `unbounded_subagent_stress_variant`: Local stress variant only: introduce dynamic participant creation. Expected `{'verdict': 'UNKNOWN', 'reason': 'DYNAMIC_TOPOLOGY'}`.
- `approval_separation_of_duty`: Separation of duty: the source requires approval before the document action, so the approving role differs from the role that creates the document. Expected `{'separated': True}`.

## What does not work / remains unverified

- SkillC cannot prove research correctness, citation quality or the quality of generated Word content.
- Frontier entitlement and effective document permissions are not observed by the offline runner.
- Dynamic participant creation outside the checker fragment yields UNKNOWN rather than certification.
- The runtime reviewer is host-supplied fixture identity, not an authenticated live Genspark user.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 02-genspark-research-word --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
