# LLM Compaction: natural-language skill → formal achievability pack

This is the **untrusted** front-end of the pipeline. An LLM reads a
natural-language skill / agent markdown and *compacts* it into a formal
**pack**: capabilities with preconditions and effects, a goal-marked global
protocol, and an initial state. The downstream checker is **sound regardless
of what the LLM produces** — a buggy compaction can only cause a *false
ACHIEVABLE* (caught later by the runtime monitor / human review), never a
false IMPOSSIBLE about the pack it actually emitted.

The compaction is exactly the "abstract away the prose into packs of
precondition / effect / deduction, then see if the goal is reachable" step.

## Trust boundary

```
   natural language  ──►  [ LLM compaction ]  ──►  pack (JSON)  ──►  [ checker ]  ──►  verdict
        (author)            UNTRUSTED                              DETERMINISTIC
                            may hallucinate                        sound for refutation
```

The checker is sound about the pack it receives, not automatically about the
source prose. An under-grant can create a correct refutation of an incorrectly
compacted pack; an over-grant can create a false positive about the real skill.
Both errors are **inspectable at one checkpoint**, which is the architectural
point. The Coq artifact proves the abstraction theorem that specifies this
asymmetry; mechanizing the exact Python symbolic transition system remains open.

## Pack schema

```jsonc
{
  "name": "string",
  "roles": ["string", ...],
  "capabilities": {
    "<cap>": {
      "owner": "<role>",
      "pre":  <formula>,          // guard; default true
      "add":  ["pred", ...],      // predicates set TRUE  (STRIPS effect)
      "del":  ["pred", ...],      // predicates set FALSE
      "assigns": {"var": <expr>}, // deterministic numeric update v := expr
      "nondet":  {"var": <formula over the NEW value>}  // v := * s.t. constraint
    }
  },
  "protocol": [ <step>, ... ],     // the goal-marked global protocol
  "goal": <formula>,
  "init_true": ["pred", ...],      // predicates true at start (frame: else false)
  "init_constraints": [ <formula>, ... ],
  "skills": {"<role>": [<local-step>, ...]} // optional role behaviours
}
```

`<step>` is one of:
```jsonc
{"act":    {"cap": "<cap>", "by": "<role>"}}        // effectful action
{"msg":    {"from":"<role>","to":"<role>","label":"<l>"}}  // communication
{"choice": {"by":"<role>","branches":{"<label>":[<step>...], ...}}}
{"goal":   <formula>}                                // explicit goal marker (optional)
{"rec":    {"name":"X","body":[<step>...]}}          // tail-recursive control
{"continue":"X"}                                     // tail position only
{"spawn":  {"role":"<role>"}}                        // outside static topology
```

A `choice` may additionally declare `"observed": true` when the medium itself
announces the selected branch, or `"external": true` for adversarial checking.
The schema gate in `src/skillc/pack.py` is authoritative for protocol and local
steps.

`<formula>`: `"pred"` | `true`/`false` | `{"and":[...]}` | `{"or":[...]}` |
`{"not":f}` | `{"cmp":[expr,"<|<=|==|>|>=|!=",expr]}`
`<expr>`: `"var"` | int | `{"+":[e,e]}` | `{"-":[e,e]}` |
`{"*":[int,e]}` | `{"*":[e,int]}`. Multiplication requires an integer constant
operand so the accepted language remains QF-LIA.

## Prompt source of truth

The live prompt is the `SYSTEM` constant in
`src/skillc/frontend/llm.py`. Keeping a second supposedly verbatim copy here
caused the documentation to drift; this document describes the interface and
trust model, while the source file defines the exact prompt.

## What compaction costs

Compaction is the **only** stage of the pipeline that spends tokens: the schema
gate and the trusted checker spend none, and neither does the deterministic
front-end. `frontend.llm.compact_measured` returns the API's own `usage` block
so that cost is measured rather than guessed, and
`compact_with_repair_measured` accumulates it across the single bounded repair
round. For a median real skill this is ~2.8K tokens — about 4% of one
successful run of the same skill, against a doomed run it avoids entirely.
See [`TOKEN_ECONOMICS.md`](TOKEN_ECONOMICS.md) and `skillc cost`.

## Live vs. reference compaction

`src/skillc/frontend/llm.py` supports Anthropic (`ANTHROPIC_API_KEY`) and Azure
OpenAI (`AZURE_OPENAI_ENDPOINT` plus either `AZURE_OPENAI_API_KEY` or the
current `az login` identity). Select the provider with `--llm-provider`; no
provider is contacted unless `--llm` is explicit. There is no silent
reference-pack fallback. The reproducible checker and corpus evaluation do not
depend on a live model because the LLM is an untrusted
producer by design.
