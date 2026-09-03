# Specification cases: the same skill, one claim achievable and one not

Nine pairs of authored skills in the checker's prose style. Variant **A** is
achievable as claimed; variant **B** makes a claim the runtime cannot honour,
and the checker names why. Each tool is a small Python script under `tools/`,
so a live agent with a shell can actually carry the skill out (A) or discover
that it cannot (B). A "done" claim on a B variant is a wrong result by
construction.

| case | B is refuted because | reason |
|---|---|---|
| `order-in-budget` | the only tool orders parts costing 350 or more; the job requires below 200 | `GOAL_UNSAT` (stated bound) |
| `quota-send` | the only tool sends campaigns costing 250 or more; the job requires below 100 | `GOAL_UNSAT` (stated bound) |
| `migrate-with-quota` | the only tool migrates at 900; the job requires below 500 | `GOAL_UNSAT` (stated bound) |
| `onboard-badge` | the job requires a badge issued and no tool issues badges | `GOAL_UNSAT` (no establisher) |
| `sign-then-ship` | the job requires a signed artifact and no tool signs | `GOAL_UNSAT` (no establisher) |
| `publish-with-approval` | `publish` requires approval and no tool approves | `BLOCKED_GUARD` |
| `two-person-release` | `release` requires a countersignature and no tool countersigns | `BLOCKED_GUARD` |
| `index-then-search` | `search_corpus` requires an index and no tool builds one | `BLOCKED_GUARD` |
| `ledger-verify` | the workflow runs `ledger_verify`, which no runtime provides | `MISSING_CAPABILITY` |

**Why the mix matters.** Only one of the nine refutations is a capability
set-difference — the kind a regular expression over the document can find. The
other eight need the checker's reachability reasoning: a bound the tools cannot
meet, a goal condition nothing establishes, a guard nothing satisfies. The
grep baseline (`scripts/grep_baseline.py`) scores 25 of 34 configurations and
is wrong on exactly those eight plus the undeclared-tool case; the checker
scores 34 of 34. The 0.2 ms is the grep's time over the 34 configurations;
the checker takes 228 ms.

**One case we dropped, and why.** A `restore-verified` pair was designed so
that B's goal named a condition (`checksummed`) no tool establishes. The
deterministic front end attributed the unestablished condition to the only
workflow step anyway, and certified it. That over-attribution is a real
precision limit of the prose reader, of the same family as the misextractions
audited in `home_refutation_audit.json`; we report it rather than tune the
reader until the case passes.
