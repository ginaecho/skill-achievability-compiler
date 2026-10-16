# Fidelity judge for the Scout arm of experiment H

Each file in `items/` is one SKILL.md and the pack gpt-5.4 compacted from it against the
`scout-desktop` runtime, written in SkillC Controlled English (`ce`, with each Tool's `via`
binding). The 20 items were chosen by sha256("scout-judge:" + case) order. Nothing in an
item says what the checker decided; do not look it up.

For every item, read `source_text` (the document) and `ce` (the pack), and answer each
rubric question with `yes`, `no` or `unclear`, plus one line saying why. The rubric is the
one pre-registered in `runs/20261015_review_response/PLAN.md` (experiment R), copied into
every item under `rubric`:

- F1: no invented Tool (every Tool corresponds to an instruction)
- F2: no omitted mandatory step
- F3: the Goal states the document's deliverable
- F4: no invented ordering (every protocol order is stated or implied by the document)
- F5: bindings plausible (each `via` names a runtime tool that can perform the Tool)

`runtime` gives the runtime's name, description and tools (needed for F5).

Write your scores to `scores.json` (or `scores_<judge>.json` for a second judge) as a JSON
list, one object per item:

```json
{"case": "c001", "F1": "yes", "F2": "no", "F3": "yes", "F4": "unclear", "F5": "yes",
  "F1_reason": "...", "F2_reason": "...", "F3_reason": "...", "F4_reason": "...",
  "F5_reason": "..."}
```

Score from the two texts only. Do not run anything, and do not open files outside this
folder.
