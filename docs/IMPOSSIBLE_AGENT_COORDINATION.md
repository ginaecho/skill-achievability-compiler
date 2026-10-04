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

## Does compaction require an LLM?

No. `skillc` needs a formal pack containing the roles, choices, messages,
capabilities, and goal, but that pack can come from three paths:

| Frontend | Best suited to | Token cost |
|---|---|---:|
| Deterministic prose compaction | Explicit prose patterns supported by the frontend | 0 |
| LLM compaction (`--llm`) | Unrestricted or less structured natural language | Provider-reported compaction usage |
| Embedded `skillc-pack` | Author-reviewed formal protocols | 0 |

The corpus descriptions for `deadlock_unobserved` and
`nonconformant_handler` are accepted by the deterministic frontend and produce
their intended protocol refutations without an LLM. The private-review example
above would normally use LLM compaction unless it were rewritten into the
deterministic frontend's recognized form or supplied as an embedded pack.

LLM compaction is an untrusted translation step. Its output must pass the
schema gate, and the deterministic checker—not the LLM—returns `ACHIEVABLE`,
`IMPOSSIBLE`, or `UNKNOWN`.

## Protocol cases in the benchmark corpus

Two impossible corpus cases are caused specifically by interaction protocols
rather than unavailable tools:

| Case | Interaction defect | Reference verdict |
|---|---|---|
| `deadlock_unobserved` | A worker privately selects `ask` or `direct`; the planner must answer only in the `ask` branch but receives no distinguishing message | `IMPOSSIBLE / NON_PROJECTABLE` |
| `nonconformant_handler` | A router may send `go_simple` or `go_complex`; the handler declares behavior only for `go_simple` | `IMPOSSIBLE / NON_CONFORMANT` |

Two real-skill semantic-validation cases also caused the LLM compactor to
propose an unobserved choice:

- `call-to-book`: an unobserved choice by the business stranded the agent.
- `prescription-refill`: an unobserved choice by the pharmacy stranded the
  agent.

Those two skills are not impossible examples. The checker rejected the
defective generated protocols, the bounded repair step corrected them, and
their final packs were `ACHIEVABLE`. They demonstrate checker-guided compaction
repair rather than early termination of impossible work.

## With and without `skillc`

The case-specific model for `deadlock_unobserved` assumes that both agents hold
context and wait until a timeout:

| Path | Tokens | Evidence |
|---|---:|---|
| With `skillc`, one-time LLM compaction | 1,888 | Modeled |
| Without `skillc`, 6-turn two-agent deadlock | 54,948 | Modeled low |
| Without `skillc`, 15-turn two-agent deadlock | 231,870 | Modeled typical |
| Without `skillc`, 30-turn two-agent deadlock | 778,740 | Modeled high |
| With deterministic compaction | 0 | By construction |

Against the typical modeled run, one-time LLM compaction is 0.81% of the
unchecked runtime tokens, or about 123x smaller. Compaction is paid once per
skill version; an unchecked deadlock pays its runtime cost on every
invocation.

The repository also publishes a generic median-skill model for both protocol
failure reasons:

| Reason | Check | Typical unchecked run | Leverage |
|---|---:|---:|---:|
| `NON_PROJECTABLE` | 2,778 | 261,900 | 94x |
| `NON_CONFORMANT` | 2,778 | 261,900 | 94x |

These figures are estimates, not measurements of interacting agent runs.

### Measured pilot limitation

The August token pilot included `deadlock_unobserved`, with 1,295 measured
compaction tokens and 274 tokens for one bounded runtime simulation. That row
does not establish protocol savings:

- LLM compaction changed the intended `NON_PROJECTABLE` defect into
  `MISSING_CAPABILITY`.
- The runtime used one monolithic simulator rather than separate planner and
  worker contexts.
- The simulator selected the favorable direct-delivery branch and reported
  achievement.

The benchmark therefore identifies the row as construct-mismatched. Likewise,
the measured `NON_CONFORMANT` result for `choice_informed_ok` was a false
refutation introduced by LLM compaction of an achievable source, so it is not
evidence of a prevented protocol failure.

The five-case real-rejection benchmark contains only missing-capability
refutations. The live-backend matrix explicitly is not a protocol-complexity
stress test. A valid measured protocol benchmark still needs separate
main-agent and subagent contexts, hidden branch selection, actual message
delivery, timeout behavior, and provider-reported usage from every
participant.

## Decision boundary

If a skill creates an unbounded number of subagents dynamically, `skillc`
normally returns `UNKNOWN`, not `IMPOSSIBLE`, because dynamic spawning leaves
the decidable fragment. An independent structural refutation can still survive
that boundary. For example, if the final mandatory action requires an
undeclared capability, `skillc` can prove `IMPOSSIBLE` regardless of how many
subagents are spawned.
