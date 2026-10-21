# Verdict coverage

A `skillc` verdict reports two separate results:

- **Goal reachability**: the `verdict` label (`ACHIEVABLE`, `IMPOSSIBLE` or
  `UNKNOWN`) and its `reason`.
- **Protocol typing**: `protocol` (`WELL_TYPED`, `REJECTED` or `NOT_CHECKED`)
  and `protocol_reason` (`NON_PROJECTABLE` or `NON_CONFORMANT`).

The checker never turns a protocol rejection into `IMPOSSIBLE`. Each verdict
names the formal result behind it: `coverage` for the goal and
`protocol_coverage` for typing. This page says what those tags mean.

## Which result covers which verdict

| Dimension | Label | Reason | `coverage` tag | What covers it |
|---|---|---|---|---|
| goal | IMPOSSIBLE | `MISSING_CAPABILITY`, `BLOCKED_GUARD`, `GOAL_UNSAT` (may semantics) | `thm1+lem3` | Theorem 1 (`refutation_sound_rel`) and Lemma 3 (`SymbolicInstance.symbolic_refutation_sound`), both mechanized in `proof/SkillAchievability.v`. Trusted, not proved: the QF-LIA denotation of pack formulas, and Z3. |
| goal | IMPOSSIBLE | same, with `context_refuted` | `thm1+lem3+establisher` | The above, plus the establisher-closure lemma: no protocol over the same capabilities reaches the goal. That lemma is proved on paper only. |
| goal | IMPOSSIBLE | `REQUIREMENT_UNAVAILABLE` | `deterministic-reader:manifest` | Not covered by Theorem 1. See "Refutations by the requirement reader" below. |
| goal | IMPOSSIBLE | any (adversarial semantics) | `paper-only:adversarial` | Proved on paper only. The mechanized theorem covers may semantics. |
| goal | UNKNOWN | `DYNAMIC_TOPOLOGY` | `thm-undec:abstention` | Abstention at the undecidability boundary. The undecidability result is proved on paper only. |
| goal | UNKNOWN | `PROTOCOL_ONLY`, `INCOMPLETE_COMPACTION`, others | `abstention` | No claim is made. |
| goal | ACHIEVABLE | `OK` | `none:witness-only` | No guarantee. A witness path exists in the abstraction (incompleteness proposition). Intent fidelity and payload faithfulness stay open. |
| protocol | REJECTED | `NON_PROJECTABLE`, `NON_CONFORMANT` | `t-comm:side-conditions;sr+sf:single-label-mechanized` | The checker decides the T-Comm side conditions (projection and conformance, then the whole-session T-Comm/T-Act/T-Goal search). Subject reduction and session fidelity are mechanized in `proof/DirectTypingSR.v`, for the single-label communication fragment only. Multi-branch choice is covered on paper. The equivalence of projection and the declarative direct judgment is an open proof obligation. |
| protocol | WELL_TYPED | none | same tag | Same scope as the row above. |
| protocol | NOT_CHECKED | none | `not-checked` | The goal was decided before the typing checks ran (missing capability, establisher-closure refutation, or dynamic spawning). |

Decidability of the static fragment is proved on paper only.

Branch assumptions (`choice.assumes`, written ``- branch `x` (assuming `p`):``) add
their facts to the world when the branch is taken, like an `add` effect; the facts
are declared by the pack, so every coverage tag above still holds relative to the
declared pack.

## Refutations by the requirement reader

`skillc check --llm --runtime M` (and `frontend.llm.decide_text`) first runs the
deterministic requirement reader `env.manifest.refute_text` on the skill text. When it finds a
hard requirement that the manifest `M` marks unavailable, the verdict is `IMPOSSIBLE` with
reason `REQUIREMENT_UNAVAILABLE`, `protocol: NOT_CHECKED` and `coverage:
deterministic-reader:manifest`. No pack is built and the checker does not run.

Theorem 1 does not cover this refutation. It rests on two things:

- the reader's requirement extraction (`env.nl.intent_from_text`): which mentions in the text
  are hard requirements and which are optional;
- the manifest's structured fields (`egress_deny`, `unavailable_programs`, `lacks`, `software`,
  see `docs/REQUIREMENT_EVALUATION.md`).

Both can be wrong. The known weak point is the first: the reader can take an optional,
alternative or example mention as a hard requirement (seven false refutations on set3, in
`docs/COMPACTION_RELIABILITY.md`). For this reason the verdict always reports the requirement
as `kind:name` in `frontier`, and the manifest entry and the evidence line from the text in
`detail`, so a person can check it. `refutation_scope` is `runtime_manifest`.

## Why a protocol rejection is not a goal refutation

Theorem 1 talks about reachability: if the abstract system cannot reach the
goal, the concrete system cannot reach it either. Typing asks a different
question. T-Comm requires *every* branch of a choice to conform. One bad
branch therefore rejects the whole protocol, even when another branch reaches
the goal.

Example: a router sends the handler either `go_simple` or `go_complex`. The
declared handler only handles `go_simple`. The `simple` branch resolves the
ticket, so the goal is reachable. The `complex` branch leaves the handler with
nothing to do, so the protocol is not well typed. The checker reports:

```text
triage: ACHIEVABLE
  ACHIEVABLE  goal reachable along witness path
  PROTOCOL REJECTED (NON_CONFORMANT): declared behaviour of role 'handler' does not
    conform to its projected contract (S_handler </= G|handler): ...
  the goal is not refuted; the coordination can deadlock, so this is not a passing check
  coverage: none:witness-only
```

Calling this `IMPOSSIBLE` would claim something that no theorem covers. It is
also false in the global semantics, because a run through `simple` reaches the
goal. The protocol is still unsafe to deploy, because the `complex` branch
can deadlock. A gate or monitor must therefore use `admissible`, not the goal
label.

## What a deployment gate should use

`admissible` is true only when the goal is `ACHIEVABLE` **and** the protocol
is not `REJECTED`. `skillc check` exits `0` only when the verdict is
admissible. `skillc gate` reports a protocol-rejected pack as `REJECTED`
(exit code 4). The runtime monitor denies such a plan and asks for a replan.
The reason text says that the goal is not refuted.

## Verdict schema v2

`skillc.verdict/2` adds these fields to `to_dict()` / `--json`:

| Field | Values |
|---|---|
| `protocol` | `WELL_TYPED`, `REJECTED`, `NOT_CHECKED` |
| `protocol_reason` | `""`, `NON_PROJECTABLE`, `NON_CONFORMANT` |
| `protocol_detail` | the failing role and branch, or `""` |
| `admissible` | `true` only for ACHIEVABLE and not REJECTED |
| `coverage` | the goal coverage tag from the table above |
| `protocol_coverage` | the protocol coverage tag from the table above |

The values `NON_PROJECTABLE` and `NON_CONFORMANT` stay in `checker.REASONS`
so that v1 consumers still parse. In v2 they appear only in
`protocol_reason`, never in `reason`.

## Corpus labels

Each corpus case now has two labels: `ground_truth` for the goal and
`protocol_truth` for typing. `deadlock_unobserved` (15-case corpus) and
`nonconformant_handler` (extended corpus) are now `ACHIEVABLE` + `REJECTED`.
Their goals are reachable in the global semantics, along the `direct` branch
and the `simple` branch respectively. Before, both cases were labelled
`IMPOSSIBLE`. The 15-case goal matrix is now TP=7, FN=0, FP=2, TN=6 (positive =
ACHIEVABLE). The protocol dimension has 0 false and 0 missed rejections.
