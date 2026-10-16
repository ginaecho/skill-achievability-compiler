# Fidelity judge (set3, PLAN.md Addendum B criterion B3, rubric F1..F5)

Each file in `items/` is one document compacted by one of two compaction methods.
File names are `<case>__<variant>.json`; the variant is `p2g` or `p2gplus`, two
versions of the compaction prompt.  Judge every item on its own, against its source
text only; do not compare the two variants of a case and do not try to tell which is
which.  Each item holds `source_text` (the original SKILL.md or agent.md), `ce` (the
final Controlled English pack the compactor, gpt-5.4, wrote for it, sample 0,
rendered with its bindings), `runtime` (the runtime it was bound to; `reply` is the
agent's own answer in the conversation) and `rubric`.  No item holds a verdict, a
truth label or a score.

The 30 documents are the first 30 in sha256("set3-judge:" + case) order among the
documents where both variants produced a valid sample-0 pack (`documents.json`).

For each of the five items in `rubric`, answer `yes`, `no` or `unclear` and give a
one-line reason that cites the document (a quoted phrase or a section) and the pack
(a Tool name, a protocol step or the Goal).

Write `scores/<case>__<variant>.json` (the same stem as the item):

```json
{"case": "c001", "variant": "p2g",
 "F1": "yes", "F1_reason": "...",
 "F2": "no",  "F2_reason": "...",
 "F3": "yes", "F3_reason": "...",
 "F4": "yes", "F4_reason": "...",
 "F5": "unclear", "F5_reason": "..."}
```

A second judge scores both variants of the 6 cases in `second_judge.json` (20% of the
30) the same way into `scores2/<case>__<variant>.json`, without reading `scores/`.
Then run `python scripts/reliability.py judge-score OUT`.

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
- A branch written `(assuming P)` states facts that hold once that branch is taken.
