# Celonis: insurance triage and fraud-analysis policy blocks

**Source category:** Official worked scenario for a planned Agent 365 partner integration

## Verifiable real use case

Microsoft gives an insurance-claims example: a malicious uploaded file is blocked via Defender, and a Fraud Agent is blocked from an unencrypted database. Celonis would connect governance activity with process context. These are explicitly documented example policies, not measurements from a named insurer.

- The worked example involves claim triage, fraud detection and customer service agents.
- It describes a malicious customer-uploaded file being blocked via Microsoft Defender.
- It describes a Fraud Agent being blocked from an unencrypted database.
- The Celonis integration itself is marked coming soon.

### Sources

- [Ecosystem partner agents available in Agent 365 - Celonis insurance scenarios](https://learn.microsoft.com/en-us/microsoft-agent-365/third-party-agents#celonis) - Microsoft Learn; verified 2026-10-13 (Primary page and both worked policy examples fetched and read directly.).

### Relationship to Agent 365

Direct, with a planned Celonis linkage: the source explicitly describes Agent 365 governance, Defender blocking and database-encryption policy.

## Complete local case

**User intent:** Triage an uploaded insurance claim and perform fraud analysis only when file-safety and encrypted-database requirements are satisfied.

**Actors:** Triage Agent, Fraud Agent and process owner; local Triage and Fraud roles model the documented actors.

**Published outcome:** Two published policy-block examples; no customer claim was processed by this evaluation.

**Modeled goal:** `fraud_analysis_completed`. This is an abstract output milestone, not proof
that the organization's business objective was achieved.

| Local capability name (not a claimed vendor API) | Workflow operation | Modeled effect |
|---|---|---|
| `triage_claim_file` | Triage the uploaded claim only after file-safety evidence is present. | `claim_triaged` |
| `connect_fraud_database` | Connect to the fraud-analysis database only when encryption evidence is present. | `fraud_database_connected` |
| `perform_fraud_analysis` | Perform the bounded fraud-analysis step using the permitted connection. | `fraud_analysis_completed` |

### Explicit local test assumptions

- The two safety predicates formalize source-stated policies but are locally declared fixture facts, not Defender or database observations.
- The serial Triage-to-Fraud handoff is a simplifying model, not a published insurer protocol.
- Runtime approval of an analysis-result operation is an added local policy.

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
   check verifies that the intent cannot manufacture `claim_triaged`.
4. The runtime checks use `ApprovalGate` at `claims.analysis.record`.
   It binds source version, content, operation and destinations, then consumes
   approval before calling a local recording function. No external system is called.

## What works

| Check | Expected result |
|---|---|
| Full declared workflow | `ACHIEVABLE` (structural admissibility only) |
| Missing `perform_fraud_analysis` grant | `IMPOSSIBLE / MISSING_CAPABILITY` |
| Final tool only queues instead of establishing `fraud_analysis_completed` | `IMPOSSIBLE / GOAL_UNSAT` |
| Skip `triage_claim_file` | `IMPOSSIBLE / BLOCKED_GUARD` for this protocol |
| Invent initial evidence | Environment wins; prerequisite stays blocked |
| Rule out every alternative plan | `UNKNOWN / PROTOCOL_ONLY` |
| Legitimate independently approved runtime operation | One local transport invocation |
| Altered payload or forged/replayed approval | Denied; zero transport calls |

- `file_safety_evidence_absent`: Source-backed policy modeled with no clean-file evidence. Expected `{'verdict': 'IMPOSSIBLE', 'reason': 'BLOCKED_GUARD'}`.
- `database_encryption_evidence_absent`: Source-backed policy modeled with no database-encryption evidence. Expected `{'verdict': 'IMPOSSIBLE', 'reason': 'BLOCKED_GUARD'}`.
- `triage_fraud_handoff_separation`: Separation of duty: Triage hands the triaged claim off to Fraud, so the first fraud-stage action (connecting to the fraud database) is owned by a role other than the one that triages the claim. Expected `{'separated': True}`.

## What does not work / remains unverified

- SkillC does not scan malware, verify TLS/database encryption or judge fraud.
- It checks the consequences of supplied evidence; adapters must establish authenticity and freshness.
- The source scenario is illustrative and the Celonis integration is marked coming soon.

The tests evaluate an authored abstraction and adversarial variants of this real
published workflow. They are **not** evidence that the named deployment is vulnerable,
uses SkillC, uses the added review policy, or was tested in a live tenant.

## Run and inspect

From the repository root:

```powershell
python examples\agent365-cases\run_cases.py --case 08-celonis-insurance-policy --write
```

`results.json` records actual verdicts, reasons, bound packs, runtime decisions and
transport counts. `case.json` preserves source metadata and local assumptions.
The shared runner returns nonzero if an expectation fails. These inputs are generated
by `build_cases.py` from the reviewed `catalog.json`; edit the catalog to regenerate.
