# SkillC and TokenMasterX: formal checking, chronology and attribution

Investigation date: November 2, 2026.

## Conclusion and attribution assessment

**SkillC's author assesses that TokenMasterX's formal-checking approach was
inspired by SkillC and borrows architectural ideas from it.** This is the
author's attribution assessment, not an independently established finding
that TokenMasterX's particular Lean proofs were derived from SkillC.

The publicly reproducible findings are narrower:

- SkillC's recorded checker implementation predates the introduction of
  TokenMasterX's Lean proof files by nearly four months.
- Both projects use formal models, explicit assumptions, conservative checks
  and gates outside the language model. Their architectural overlap is real,
  even though their proof languages and checked properties differ.
- Direct use of the SkillC compiler was not found in the traced TokenMasterX
  implementations.
- The public source and chronology alone do not establish which mechanisms
  were borrowed, the origin of each proof, or a causal relationship.

Different implementations do not rule out conceptual influence. Conversely,
shared formal-methods techniques and an earlier implementation do not, on
their own, prove that a later project derived its architecture from it.
This note does not assert plagiarism or code copying.

## Verified chronology

| Event | Recorded UTC time | Primary evidence |
|---|---|---|
| SkillC checker implementation | July 1, 2026, 20:36:31 | [SkillC commit `9b670258`](https://github.com/ginaecho/skill-achievability-compiler/commit/9b6702585ed429feeffbfbb063d92f2c8e48d178) |
| TokenMasterX Lean proof PR opened | October 29, 2026, 02:27:44 | [All-The-Vibes/TokenMasterX#17](https://github.com/All-The-Vibes/TokenMasterX/pull/17), `createdAt` |
| TokenMasterX Lean introduction commit | October 29, 2026, 03:18:24 | [TokenMasterX commit `575496c1`](https://github.com/All-The-Vibes/TokenMasterX/commit/575496c1a5c2f970016a6c94faef103d2ab07cce) |
| Lean proof PR merged into `main` | October 29, 2026, 03:18:25 | The same PR's `mergedAt` and matching `mergeCommit` |

The TokenMasterX commit's author and committer fields both read
`2026-10-28T22:18:24-05:00`. That is October 29 at 03:18:24 UTC; the October 28
date is a timezone difference, not a separate earlier introduction.
At UTC+1, the PR merged on October 29 at 04:18:25.

The inspected TokenMasterX clone is not shallow. The first additions of
`.lean` files in its `main` history occur at `575496c1`, titled
"Prove the core claims in Lean 4 and fix the four that did not hold."
Its parent has no `proofs` directory. The commit adds eight proof modules,
the entry module, documentation and Lean project/toolchain files.

This establishes the recorded introduction into that history, not the
earliest possible private work on Lean proofs. SkillC's Git timestamps
likewise record repository chronology, not independent certification of
first public availability or priority over formal verification as a field.

## What the projects actually check

| Aspect | SkillC | TokenMasterX |
|---|---|---|
| Principal question | Can a declared task reach its goal under the declared capabilities, guards and effects? | Can context transformations and token-reduction policies meet their declared constraints? |
| Intermediate representation | Roles, capabilities, preconditions, effects, protocol, initial state and goal | Typed request policies and canonical message representations |
| Formal work | Coq specification/proofs and a Z3-backed guarded-effect reachability checker | Lean models of cache prefixes, shaping bounds, reversible folds, routing and measurement |
| Feasibility | Structural admissibility of a goal-reaching abstract run | Whether specified statistical sample bounds could satisfy an acceptance gate |
| Runtime checks | Approved plans, capabilities, preconditions, execution facts and rechecking | Resource identity, provenance, request budgets, narrow action contracts and policy promotion |

TokenMasterX is not merely a prompt convention. Some checks genuinely block
dispatch, tool delivery or policy promotion outside the model. The shared
ideas include explicit assumptions, conservative admission, evidence bound to
a configuration, and checks performed outside the model's own instructions.

However, a Lean theorem about cache-prefix preservation or token non-expansion
is not a theorem that an agent's task goal is reachable. The inspected
TokenMasterX paths do not implement SkillC's capability/effect/protocol
reachability judgment.

SkillC's `ACHIEVABLE` means structural admissibility, not guaranteed concrete
success. Its `IMPOSSIBLE` verdict is relative to the declaration and
abstraction assumptions; `UNKNOWN` is abstention. Those qualifications are
essential to a fair comparison.

## Source references

SkillC comparison revision:
`39334797a537e9ec810aae292651ac59a68a73f2`.

- [Formal pack model](https://github.com/ginaecho/skill-achievability-compiler/blob/39334797a537e9ec810aae292651ac59a68a73f2/src/skillc/pack.py#L1-L51).
- [Independent environment-grant binding](https://github.com/ginaecho/skill-achievability-compiler/blob/39334797a537e9ec810aae292651ac59a68a73f2/src/skillc/frontend/grants.py#L21-L52).
- [Checker semantics and limitations](https://github.com/ginaecho/skill-achievability-compiler/blob/39334797a537e9ec810aae292651ac59a68a73f2/src/skillc/checker.py#L1-L59).
- [Runtime monitor boundaries](https://github.com/ginaecho/skill-achievability-compiler/blob/39334797a537e9ec810aae292651ac59a68a73f2/src/skillc/monitor.py#L1-L58).

TokenMasterX comparison revision:
`c681a8d6568a566dcdae58970768e49c8baf92bb`.

- [Cache proof model](https://github.com/All-The-Vibes/TokenMasterX/blob/c681a8d6568a566dcdae58970768e49c8baf92bb/proofs/TokenMasterProofs/Cache.lean#L136-L193).
- [Token-shaping proof model](https://github.com/All-The-Vibes/TokenMasterX/blob/c681a8d6568a566dcdae58970768e49c8baf92bb/proofs/TokenMasterProofs/Shaping.lean#L23-L79).
- [Statistical plan feasibility](https://github.com/All-The-Vibes/TokenMasterX/blob/c681a8d6568a566dcdae58970768e49c8baf92bb/token-master-plugin/skills/token-master/brainspace/plan_feasibility.py#L25-L122).
- [Statistical certification gate](https://github.com/All-The-Vibes/TokenMasterX/blob/c681a8d6568a566dcdae58970768e49c8baf92bb/token-master-plugin/skills/token-master/brainspace/certification.py#L526-L587).
- [Narrow native-runtime enforcement](https://github.com/All-The-Vibes/TokenMasterX/blob/c681a8d6568a566dcdae58970768e49c8baf92bb/token-master-plugin/skills/token-master/brainspace/native_runtime.py#L182-L295).

## Method and limitations

The implementation review used 711 selected text/source files, with addresses
scrubbed before delegated inspection. It traced central implementation paths,
formal proof statements and representative tests as source. It did not inspect
every omitted binary, external dependency or historical file version.
No direct SkillC identifiers were found in that selected source; this absence
is not proof of no influence.

The Lean introduction chronology was separately checked using full local Git
history, the parent/commit file lists and GitHub PR metadata.
No TokenMasterX code, dependency installer, benchmark, live model call or
Lean proof build was executed. This is source inspection and evidence
comparison, not independent proof-build certification.
