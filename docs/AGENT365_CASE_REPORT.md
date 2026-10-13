# Agent 365: ten source-backed cases and SkillC improvements

Date: **2026-10-13**. Branch: `gc/A365`.

## Delivered

Ten complete folders under [`examples/agent365-cases`](../examples/agent365-cases/README.md):
KPMG governance, Genspark research/Word, Zendesk support, Rox sales insights,
Gloat opportunities, Kasisto governed banking agents, Egnyte summaries, Celonis
insurance policies, Sophos incident response and Adobe marketing review.
Each includes valid primary-source links, source/availability labels, requirements,
independent environment contracts, executable checks, results and limitations.

**Evidence qualification:** these are published workflows, not ten verified live
customer deployments. KPMG is an adoption announcement; six are documented partner
workflows; Egnyte, Celonis and Adobe are marked **coming soon**. The weaker Integra
and Cowork candidates were excluded from the final selection. All final sources
explicitly link the relevant organization/product to Agent 365.

## What was fixed

While preparing the cases, a regression test reproduced a bug in
`src/skillc/frontend/contracts.py`: applying environment contracts **unioned**
the intent's initial facts with the environment's facts. An intent could therefore
claim prior approval or completed prerequisite work that the environment did not
declare, allowing an otherwise blocked modeled action.

Environment `init_true` now **replaces** intent-supplied initial facts when contracts
are applied. The fix preserves source input without mutation. A focused regression
failed before the fix and passes afterward; all ten cases also exercise invented
initial evidence. The trusted checker and its proof scope were not changed.

## Observed results

- **123/123 case checks matched expectations:** 63 static and 60 runtime.
- Static results: **10 ACHIEVABLE, 42 IMPOSSIBLE, 11 UNKNOWN**. Positive results
  mean structural admissibility; `UNKNOWN` is not counted as prevention.
- Runtime results: **10 allowed, 50 denied** attempted operations. Denied attempts
  invoked no transport. Replay tests have a separate successful setup invocation.
- **129 targeted regression tests passed**, covering the case corpus, contracts,
  grant binding, prior review regressions and Execution Atlas callers.
- No live customer, Microsoft 365 or partner API calls were made by the runner.

Machine-readable evidence: [summary](../examples/agent365-cases/summary.json) and
each folder's `results.json`, including the actual bound packs and reasons.
These are local, authored abstractions with controlled variants, not a benchmark
of natural-language compaction or real deployment success.

## What SkillC can and cannot establish

It can refute missing modeled capabilities, absent effects and blocked prerequisites,
distinguish a bad protocol from an impossible goal, and enforce the existing
evidence-bound approval gate at a wrapped operation. The Celonis cases check the
consequences of declared file-safety/encryption evidence, not malware or encryption
themselves.

Still outside scope: live permissions and entitlement discovery, authenticated
cross-agent receipts, source freshness, business/content correctness, actual
transport execution and verified Agent 365/Purview telemetry ingestion.
The existing approval gate requires a trusted host to supply real identities and
current artifacts. No claim is made that the named products have the tested flaws.
