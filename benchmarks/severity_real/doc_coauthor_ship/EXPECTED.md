# EXPECTED: doc_coauthor_ship

Written BEFORE the tool was run on any real pack (pre-registration; see git history).
Analysis: `skillc severity pack.json`, kmax = 4. Reasoning below is by hand from the pack
and the source files' stated behaviour, not from tool output.

## Reading rule (from the paper's Definition of severity, kmax = 4)

A branch the guard marks as intended is reported Benign. A misselected branch is
Catastrophic iff, from its residual, an irreversible action can fire with the goal
already unreachable within at most 4 further misselections; otherwise Futile if the goal
is unreachable from the residual, otherwise Benign. Verdicts are per branch and per
abstract world, so a loop contributes one verdict per world state it is visited in.
The table below is evaluated against each reported verdict: `condition` is a Python
boolean over the pack's atoms (true atoms in the verdict's state); the first matching row
for the verdict's branch label applies; an empty condition always matches.

## Summary expectations

- k*: 0
- PNR: ship
- static choice points: 1
- irreversible tools: ship (declared)
- bystander: Acts follow messages addressed to their owners (write_draft after DocRequest, apply_brand_style after StyleRequest, revise_draft after the feedback messages); `reader_test` opens the loop body and `ship` follows the loop: expected 0 pairs, exact.

Why k* = 0: With 0 misselections the loop revises once and then styles; one wrong `style` at the first visit reaches `ship` with gaps open.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| reader_feedback |  | Benign | intended while gaps are open; once revised it is a wasted round with no hazard reachable (style then ship is safe) |
| style | draft_revised | Benign | intended: the reader test no longer surfaces gaps |
| style | not draft_revised | Catastrophic | styling and shipping an announcement whose gaps were never fixed: `ship` fires with the goal lost |
