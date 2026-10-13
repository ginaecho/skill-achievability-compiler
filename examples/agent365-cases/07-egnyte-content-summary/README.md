# Egnyte: enterprise file summaries and collaboration in Teams

**Source category:** Documented planned Agent 365 partner workflow

## Verifiable real use case

Microsoft's Egnyte entry describes scanning files in Egnyte storage, summarizing or generating content and collaborating in Teams conversations. The integration is explicitly marked coming soon, so this is a published planned workflow rather than a verified deployed customer case.

- The described agent scans files in Egnyte storage to summarize or generate content.
- Users collaborate on that content in Teams one-to-one and group conversations.
- Microsoft explicitly marks the Egnyte Agent 365 integration as coming soon.

### Sources

- [Ecosystem partner agents available in Agent 365 - Egnyte](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#egnyte) - Microsoft Learn; verified 2026-10-13 (Primary page and Egnyte section fetched and read directly, including availability caveat.).

### Relationship to Agent 365

Direct but planned: Microsoft explicitly names the integration and says it is coming soon.

## Complete local case

**User intent:** Read the relevant enterprise files, summarize their content and share the summary in the intended Teams conversation.

**Actors:** Employee, Egnyte content agent and conversation participants; abstract Agent role.

**Published outcome:** Published intended content collaboration behavior; current availability and customer results are not verified.

**Modeled goal:** `content_summary_shared`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `scan_egnyte_files` | Scan the relevant files in Egnyte storage. | `files_scanned` |
| `summarize_enterprise_content` | Summarize the scanned enterprise content. | `content_summary_ready` |
| `share_content_summary` | Share the summary in the intended Teams conversation. | `content_summary_shared` |

### Explicit local test assumptions

- The declared environment assumes file access and Teams presentation capabilities for testing; it does not claim the planned integration is live.
- The runtime source fixture represents an immutable snapshot or manifest of all contributing files, not an actual Egnyte folder.
- Independent approval and an exact conversation allowlist are added local safeguards.

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
   check verifies that the intent cannot manufacture `files_scanned`.
4. The runtime checks use `ApprovalGate` at `teams.content.share`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `share_content_summary` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `content_summary_shared` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `scan_egnyte_files` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |



## What does not work / remains unverified

- The planned integration's live availability is unverified.
- The host must bind all contributing source versions; SkillC cannot detect an unseen remote file change.
- Summary fidelity, legal privilege, document classification and effective file permissions need additional systems.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 07-egnyte-content-summary --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
