# Specification cases: the same skill, one claim achievable and one not

Four pairs of authored skills in the checker's prose style. Variant **A** is
achievable as claimed; variant **B** makes a claim the runtime cannot honour,
each for a different reason the checker names:

| case | B is refuted because | checker reason |
|---|---|---|
| `order-in-budget` | the only tool orders parts costing 350 or more; the job requires below 200 | `GOAL_UNSAT` (a stated bound the budget cannot meet) |
| `publish-with-approval` | `publish` requires approval and no tool approves | `BLOCKED_GUARD` |
| `onboard-badge` | the job requires a badge to be issued and no tool issues badges | `GOAL_UNSAT` (no establisher) |
| `ledger-verify` | the workflow runs `ledger_verify`, which no runtime provides | `MISSING_CAPABILITY` |

Every tool is a small Python script under `tools/`, so a live agent with a
shell can actually carry the skill out (variant A) or discover that it cannot
(variant B). `scripts/usefulness_spec_tasks.json` gives each variant a task
and a verifier that checks the artifact the tool would produce; a "done" claim
on a B variant is a wrong result by construction.
