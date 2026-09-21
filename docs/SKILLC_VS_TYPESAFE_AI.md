# SkillC vs. TypeSafe AI: A Complete Comparison

**Assessment date:** 2026-09-21.
**Conclusion:** TypeSafe AI's Jev is an adjacent product and a potential
complement to SkillC, not a direct substitute for its static achievability
checker. There is meaningful overlap in the market for reliable AI automation,
but the documented mechanisms and guarantees address different problems.

This comparison uses TypeSafe's first-party website, documentation, launch
article, and accessible X content. SkillC's baseline is the repository
documentation at commit `47ebb3b`, especially the [README](../README.md),
[domain glossary](../CONTEXT.md), and [paper scope](../paper/README.md).
Uncommitted compiler experiments are not evidence of established features.
Product descriptions are distinguished below from vendor performance claims
and proposed integrations.

## 1. Executive assessment

TypeSafe asks: **How can AI make a narrow judgment that software can consume
directly?** Jev accepts context and typed questions, then returns decisions
and probabilities. Application code composes those decisions into workflows.
Its documented architecture is runtime model inference, not a static
workflow checker and not an autonomous verification-agent loop. [T2][T3]

SkillC asks: **Does a declared skill admit a goal-reaching abstract execution
under its declared capabilities and protocol?** Its trusted checking path uses
deterministic analysis and Z3 rather than an AI model's judgment. An optional,
untrusted LLM front end can translate prose into the formal pack. Its positive
verdict means structural admissibility, not guaranteed real-world success. [S1][S2]

The defensible positioning is:

> TypeSafe supplies typed probabilistic decisions inside software. SkillC
> analyzes whether the declared system containing those decisions, tool
> interactions, guards, and goals is structurally achievable.

Neither result substitutes for the other. A correctly typed decision can
select an ineffective action; a structurally admissible workflow can fail
because the backend is unavailable or the model's judgment is wrong.

## 2. What TypeSafe AI actually provides

Jev is TypeSafe's first public "System One" model. A request to
`POST /v1/systemone` supplies `state`, a model identifier, and named typed
questions. The documented interface accepts text, including structured JSON
containing text, rather than image/audio/video input. Independent questions
are evaluated against the same state in parallel. [T2][T4][T8]

| Primitive | Purpose | Response |
|---|---|---|
| `Choice` | Select from caller-defined options | Selected option, probabilities across options, and confidence |
| `Score` | Evaluate against ordered rubric levels | Probability-weighted score, probabilities across levels, and confidence |
| `Noul` | Evaluate a yes/no question | A number from 0 to 1 representing the probability of yes |

These are the documented API shapes, not examples of a general program
verification language. A Score can lie between rubric levels. Noul does
**not** carry the separate `confidence` field returned for Choice and Score. [T4][T5]

### Static checking, runtime validation, or another agent?

There are three different mechanisms to distinguish:

| Layer | What the evidence supports | What it does not establish |
|---|---|---|
| SDK typing | The JavaScript/TypeScript SDK supplies declarations and infers answer types from questions | Proof of a complete workflow's behavior |
| API validation | Malformed request bodies can return HTTP `422` | Proof that a well-formed question has a correct answer |
| Runtime inference | Jev produces constrained decisions/probabilities over the supplied answer space | Static protocol conformance or goal reachability |

The SDK's ordinary TypeScript support is real static typing, but **it is not
the main decision mechanism and is not equivalent to SkillC's analysis**.
JavaScript execution itself does not acquire TypeScript compile-time checks.
This assessment does not assume undocumented SDK response-validation
behavior. [T4][T6]

Conceptually:

```text
Application code supplies state and typed questions
    -> API validates the request
    -> Jev performs runtime inference
    -> structured decisions and probabilities
    -> application code applies rules and chooses the next operation
```

TypeSafe explicitly recommends keeping control flow, deterministic rules,
and side effects in application code. Its model does not choose its own
next action. The reviewed sources provide no evidence that a second
autonomous agent is required to verify each answer, or that Jev uses MPST,
SMT, or pre-execution reachability analysis to validate workflows.
This is a statement about the documented product, not a claim to know every
detail of its proprietary implementation. [T3][T4]

Jev can also be used to judge another model's output or power a guardrail.
That remains a runtime model-based judgment, not a mathematical proof. [T7]

### Output types are not semantic truth

TypeSafe describes outputs as type-safe by construction: the model answers
within a predefined output space rather than generating arbitrary prose.
Its launch article associates its "no hallucinations" claim with schema
matching. This does **not** establish that every selected answer is true
or every action based on it is safe. [T3][T7]

TypeSafe's documentation explicitly says calibration is measured across
groups of predictions and does not guarantee that an individual answer is
correct. Choice/Score confidence is derived from the answer's probability
distribution; it is not an independent verifier's approval. [T5][T10]

RLCD, or Reinforcement Learning for Calibrated Decisions, is TypeSafe's
description of its training method. The reported speed/cost improvements
are vendor benchmark claims about System One-shaped tasks, not independent
evidence of universal superiority. The launch article qualifies its
headline gains and uses reference-model predictions in its workflow
evaluations. They should not be compared directly with SkillC's
avoided-execution token savings: those measure different interventions. [T1][T7]

## 3. What SkillC actually establishes

A formal pack declares capabilities, preconditions/effects, a protocol,
initial state, a goal, and optionally role behaviors. The executable checker
checks capability coverage, protocol realizability, role conformance, and
goal may-reachability. Its front ends include deterministic markdown
extraction, embedded formal packs, and optional LLM compaction. [S1]

| Verdict or boundary | Correct interpretation |
|---|---|
| `IMPOSSIBLE` | A refutation relative to the declared pack and the abstraction's assumptions |
| `ACHIEVABLE` | An abstract goal-reaching path is admitted; concrete success is not guaranteed |
| `UNKNOWN` | Abstention outside the supported decision boundary, not a refutation |
| Intent fidelity | The formal goal must reflect the human's intended goal |
| Payload faithfulness | Declared effects must faithfully model actual tool behavior |

The last two obligations are not discharged merely by passing the static
checker. A schema-valid but unfaithful LLM-generated pack can misrepresent
the source skill. Soundness about that pack is not automatically soundness
about the original prose or deployed service. [S1][S2]

The paper's direct whole-session typing judgment and the executable
projection-based conformance adapter must also be distinguished. Their
equivalence is an open mechanization obligation. Coq developments establish
identified theorem fragments; they do not constitute verification of the
entire Python checker or its exact symbolic transition system. [S3]

SkillC is not itself a runtime orchestrator. It can be invoked as an admission
gate by a runtime or CI system, but that integration must act on the verdict.
It does not automatically fetch backend data, execute a recovery policy, or
monitor a live deployment merely because it checked a pack. [S1][S2]

### May-achievability versus resilience to failures

The default analysis is existential: a goal-reaching abstract path can exist
even when another branch fails. **It does not require every failure branch
to recover.**

The implementation additionally documents `--adversarial`: choices explicitly
marked `"external": true` are environment-controlled, while agent choices
remain existential. This asks a stronger question about surviving the modeled
external branch choices. It is an implementation-only extension, not part of
the current paper revision's core claims. Do not generalize it to all numeric
nondeterminism, all real-world outages, or probabilistic success guarantees. [S1][S3]

Both modes require the relevant outcomes to be represented. An undeclared
timeout, permission failure, or schema change is not automatically explored.
Static topology and dynamic spawning also matter: spawning can move the
problem outside the decidable fragment and yield `UNKNOWN`, unless an
independent structural refutation already applies. [S1][S2]

## 4. Side-by-side comparison

| Dimension | TypeSafe AI / Jev | SkillC |
|---|---|---|
| Primary artifact | Model/API and SDKs | Compiler/checker and formal packs |
| Main time of operation | Inference during application execution | Before executing the declared skill |
| Subject | A judgment over supplied state | A declared protocol, capabilities, effects, and goal |
| Output | Typed decisions, probabilities, and applicable confidence fields | Verdict, diagnostic evidence, and applicable abstract witness |
| Main mechanism | Learned inference with constrained output space | Deterministic protocol/capability analysis and SMT reachability |
| Meaning of "types" | Per-call answer shapes/options | Communication/conformance discipline plus goal-achievability analysis |
| Backend availability | No whole-system availability proof documented | Checks declared capability coverage, not live service health |
| Semantic correctness | Not guaranteed by calibration or output typing | Real tool behavior remains a modeling/runtime obligation |
| Workflow ownership | Application code owns control flow | The consuming runtime must enforce the admission decision |
| Second AI verifier required | Not documented | No model in the trusted checking path |

Sources: TypeSafe architecture, API, confidence, and SDK documentation
[T2]-[T6]; SkillC README, glossary, and paper scope [S1]-[S3].

## 5. Applying the distinction to a Bosch-style backend failure

Consider the reported pattern, without assuming details of any proprietary
Bosch system:

```text
Fetch data from a backend -> call an LLM with that data -> deliver a result
                     |
                     +-> fetch fails -> workflow stops
```

Stopping can be the **correct** behavior if fresh backend data is required.
Neither product should be used to justify silently continuing with invented
data or an unauthorized substitute.

**TypeSafe's contribution:** after data is available, Jev could classify or
score its meaning, or help route a request. If the backend fails before
inference, substituting Jev for an LLM does not fix that dependency.
HTTP status, authentication, schema validation, and retry counters should
normally remain deterministic application logic rather than fuzzy model
judgments. This follows TypeSafe's own recommendation to use code where
deterministic rules suffice. [T3]

**SkillC's contribution:** given an adequate declaration, it can expose missing
capabilities, unreachable goals, unsatisfiable guards, and protocol/conformance
problems before the workflow spends execution resources. It can also analyze
an explicitly declared error-handling policy. [S1]

For example, the declaration might distinguish:

| Modeled outcome | Declared behavior | Requirement to preserve |
|---|---|---|
| Successful fetch | Continue to analysis | Valid data is available |
| Timeout | Bounded retry, then an approved fallback | Retry budget and freshness constraints |
| Authorization failure | Stop or request authorized intervention | No credential or policy bypass |
| No permitted data source | Report inability to complete | Do not claim the original data-dependent goal was achieved |

These are **proposed modeling choices**, not existing SkillC YAML syntax or
automatically generated recovery code. A declarative workflow adapter would
need to encode them into the supported pack semantics.

If the success path reaches the goal but the timeout path stops, default
may-analysis can still admit the workflow. Adversarial analysis over an
explicit external success/timeout choice can expose that the goal is not
maintainable under all those outcomes. A failure notification is not success
unless the declared goal explicitly permits it; weakening the goal must not
be presented as preserving the original requirement.

## 6. Proposed integration

An integration could retain both technologies at their appropriate layers:

```text
Workflow declaration + capability contracts + goal
    -> adapter produces a SkillC pack
    -> static admission check
    -> approved workflow executes in its existing runtime
         -> backend calls and deterministic error handling
         -> Jev for selected semantic decisions
         -> runtime validation and monitored effects
```

This is a proposal, not a shipped SkillC-TypeSafe integration.

The work required would include:

1. **Contract mapping.** Represent each relevant backend/MCP/Jev operation
   using explicit preconditions, effects, allowed outcomes, and role ownership.
   An MCP input/output schema alone does not provide its semantic effects.
2. **Supported numeric representation.** SkillC's current formula language
   uses integer linear arithmetic. A raw confidence such as `0.8` cannot
   simply be inserted as a supported numeric literal. Use an explicit
   predicate or a documented, conservative integer encoding; review rounding
   and threshold boundaries. See [formula validation](../src/skillc/formula.py).
3. **Uncertainty modeling.** Include low-confidence, invalid-input, API-error,
   and timeout paths where relevant. Do not treat a high score as proof of
   truth or replace environmental uncertainty with a guaranteed effect.
4. **Runtime enforcement.** Existing application code must implement the
   declared guards and responses, validate actual payloads, and handle failures.
5. **Change control.** Recheck affected packs when contracts or workflows
   change. TypeSafe documents moving model aliases and recommends version
   pinning when thresholds have been tuned to a particular model. [T8]

Extensibility is therefore a sound direction for SkillC, but "a compiler for
any project" is too broad without qualification. New domains need front ends
and faithful capability contracts, and must respect the supported language
and decidability boundary. Tool discovery or association can help construct a
candidate contract; it does not establish that the contract is true.

## 7. Competition and positioning

| Assessment area | Judgment | Basis |
|---|---|---|
| Direct functional substitution | Low on current evidence | Typed runtime decisions do not replace static goal analysis |
| Buyer attention and messaging overlap | Meaningful | Both address reliable, lower-cost AI automation |
| Integration potential | Strong architectural fit, unimplemented | A typed decision model can be one capability in a checked workflow |
| Future competitive risk | Conditional | Would increase if TypeSafe adds capability contracts and pre-execution workflow verification |
| Research contribution overlap | Limited in reviewed materials | Different objects of analysis and different guarantees |

These are analytical judgments, not market-share measurements or claims
about an unpublished roadmap.

SkillC should lead with **capability-relative goal achievability and explicit
trust boundaries**, not the ambiguous promise of "type-safe AI." TypeSafe's
important contribution is efficient machine-consumable inference; it should
not be dismissed as merely JSON validation. Conversely, its use of typed
outputs should not be described as a substitute for protocol verification.

Recommended next work is a small, explicitly scoped backend-dependency
example with unchanged business goals, declared success/failure outcomes,
and both may and adversarial results. Any Jev integration should be evaluated
separately for model quality/calibration and for workflow-level behavior.
There is no basis here for claiming either product guarantees backend uptime
or eliminates all failed executions.

## 8. Evidence limits and corrections

- TypeSafe's official homepage links to `@typesafeai` on X. The accessible
  X response contained a truncated launch preview without a visible post
  permalink or timestamp. Individual X claims and dates are not independently
  established here. [T1][T9]
- Public docs describe the product interface, not every proprietary model
  implementation detail. Absence of documented MPST/SMT checking is not proof
  that no internal experiment or future roadmap exists.
- Performance, price, and calibration claims were not independently
  benchmarked for this assessment. Pricing and availability can change.
- SkillC's paper and implementation scopes differ. This comparison is not a
  fresh proof audit or a certification of pending compiler changes.
- Earlier descriptions that implied automatic MCP semantic discovery,
  automatic recovery synthesis, a fully verified Python checker, or a
  requirement that every default may-analysis branch reach the goal were
  too strong. Those claims are not adopted here.
- Earlier illustrative SDK calls are not implementation guidance. Use the
  current official SDK/API documentation rather than treating conceptual
  pseudocode as executable code.

## Sources

TypeSafe primary sources, accessed 2026-09-21:

- [T1: Official homepage](https://typesafe.ai/)
- [T2: Introduction](https://docs.typesafe.ai/introduction)
- [T3: How to build with TypeSafe](https://docs.typesafe.ai/concepts/how-to-build-with-system-one)
- [T4: HTTP API reference](https://docs.typesafe.ai/api)
- [T5: Confidence](https://docs.typesafe.ai/confidence)
- [T6: JavaScript/TypeScript SDK](https://docs.typesafe.ai/sdk/javascript)
- [T7: Introducing System One Models & Jev, dated September 15, 2026](https://typesafe.ai/blog/introducing-system-one-models-and-jev)
- [T8: Models, versioning, and input limits](https://docs.typesafe.ai/models)
- [T9: Official X account, limited accessible content](https://x.com/typesafeai)
- [T10: System One and calibration limits](https://docs.typesafe.ai/concepts/system-one)
- [Documentation index](https://docs.typesafe.ai/llms.txt)
- [Architectural patterns](https://docs.typesafe.ai/patterns)

SkillC primary sources, baseline `47ebb3b`:

- [S1: README and implementation-only extensions](../README.md)
- [S2: Domain model and trust-boundary vocabulary](../CONTEXT.md)
- [S3: Paper scope and relation to Coq developments](../paper/README.md)

[T1]: https://typesafe.ai/
[T2]: https://docs.typesafe.ai/introduction
[T3]: https://docs.typesafe.ai/concepts/how-to-build-with-system-one
[T4]: https://docs.typesafe.ai/api
[T5]: https://docs.typesafe.ai/confidence
[T6]: https://docs.typesafe.ai/sdk/javascript
[T7]: https://typesafe.ai/blog/introducing-system-one-models-and-jev
[T8]: https://docs.typesafe.ai/models
[T9]: https://x.com/typesafeai
[T10]: https://docs.typesafe.ai/concepts/system-one
[S1]: ../README.md
[S2]: ../CONTEXT.md
[S3]: ../paper/README.md
