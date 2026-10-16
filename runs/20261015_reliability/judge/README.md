# Fidelity judge (experiment R, PLAN.md F1..F5)

Each file in `items/` is one document: `source_text` is the original SKILL.md or
agent.md, `ce` is the final Controlled English pack the compactor (gpt-5.4, P2g
sample 0) wrote for it, and `runtime` is the runtime it was bound to.  The item
holds no verdict, no truth label and no score: judge the pack against the source
text only.

For each of the five items in `rubric`, answer `yes`, `no` or `unclear` and give a
one-line reason that cites the document (a quoted phrase or a section) and the
pack (a Tool name, a protocol step or the Goal).

Write `scores/<case>.json`:

```json
{"case": "c001",
 "F1": "yes", "F1_reason": "...",
 "F2": "no",  "F2_reason": "...",
 "F3": "yes", "F3_reason": "...",
 "F4": "yes", "F4_reason": "...",
 "F5": "unclear", "F5_reason": "..."}
```

A second judge scores 20% of the items (the cases in `second_judge.json`) the same
way into `scores2/<case>.json`, without reading `scores/`.  Then run
`python scripts/reliability.py judge-score OUT`.

Notes for judging:
- F1: a Tool is invented when no sentence of the document asks for that operation.
- F2: a step is mandatory when the document's core deliverable cannot be produced
  without it; optional or follow-up work may be omitted or skippable.
- F3: the Goal must name the deliverable of one representative request.
- F4: an ordering is invented when the protocol puts two steps in an order the
  document neither states nor implies (e.g. by data dependence).
- F5: `via` must name a runtime tool from `runtime.tools` that can really perform
  the Tool; a `via` naming something outside that list is plausible only if the
  runtime indeed cannot perform the operation.
