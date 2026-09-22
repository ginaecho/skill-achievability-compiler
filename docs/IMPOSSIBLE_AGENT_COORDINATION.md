# Impossible Agent Coordination

`skillc` does more than check whether a skill invokes available tools. It can
statically validate goal reachability, guarded preconditions, numeric
constraints, and interactions among a main agent and subagents.

The following skill declares every capability it needs. It is nevertheless
impossible because one agent must react to a choice that it cannot observe.

## Natural-language skill

```markdown
---
name: private-review-routing
description: Review a change by privately selecting either security or performance analysis, then have an editor publish the appropriate report.
---

# Private review routing

Participants: a **main agent**, a **reviewer**, and an **editor**.

The task is complete when the editor has published the final report.

## Capabilities

- `security_review`, owned by the reviewer, produces `security_findings`.
- `performance_review`, owned by the reviewer, produces
  `performance_findings`.
- `publish_security`, owned by the editor:
  - requires `security_findings`
  - produces `report_published`
- `publish_performance`, owned by the editor:
  - requires `performance_findings`
  - produces `report_published`

## Workflow

1. The main agent privately chooses either:
   - **security**: ask the reviewer to perform `security_review`; or
   - **performance**: ask the reviewer to perform `performance_review`.
2. The editor is not told which branch was selected.
3. The editor must publish the corresponding report:
   - use `publish_security` for the security branch;
   - use `publish_performance` for the performance branch.

The task finishes when `report_published` is true.
```

## Why the declared interaction is impossible

The problem is not a missing tool. All four capabilities are declared. The
problem is that the editor's required behavior depends on private state held by
the main agent:

```text
main agent privately chooses branch
              |
              +-- security ---- reviewer creates security findings
              |
              +-- performance - reviewer creates performance findings

editor receives no branch information
              |
              +-- must nevertheless choose the matching publication action
```

The editor must call `publish_security` in one branch and
`publish_performance` in the other. Because the editor receives no message
distinguishing those branches, the global protocol cannot be projected into a
realizable local contract for the editor.

The expected refutation is:

```text
private-review-routing: IMPOSSIBLE [NON_PROJECTABLE]
  role 'editor' must behave differently across an unobserved choice
```

An integrating runtime can use this result as a pre-execution gate. It avoids
launching the reviewer and editor, generating a review, waiting on an
unresolvable handoff, and spending more tokens on retries.

## Repair

Make the selected branch observable:

```markdown
After choosing, the main agent sends the editor exactly one message:

- `publish_security_report`, or
- `publish_performance_report`.

The editor selects its publication action from that message.
```

The interaction then has a realizable handoff:

```text
main agent chooses
    +-- tells editor "publish_security_report"
    +-- tells editor "publish_performance_report"
```

This is a protocol repair rather than a capability repair. Adding another tool
would not tell the editor which existing action to perform.

## Decision boundary

If a skill creates an unbounded number of subagents dynamically, `skillc`
normally returns `UNKNOWN`, not `IMPOSSIBLE`, because dynamic spawning leaves
the decidable fragment. An independent structural refutation can still survive
that boundary. For example, if the final mandatory action requires an
undeclared capability, `skillc` can prove `IMPOSSIBLE` regardless of how many
subagents are spawned.
