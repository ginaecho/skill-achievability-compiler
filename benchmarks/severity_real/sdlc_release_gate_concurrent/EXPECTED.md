# EXPECTED: sdlc_release_gate_concurrent

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
- PNR: deploy
- static choice points: 1
- irreversible tools: deploy (declared)
- bystander: `address_comments` follows ReviseAuthor (addressed to Author) and `deploy` follows Deploy (addressed to DevOps): expected 0 pairs, exact.

Why k* = 0: One correct revise round fixes the findings; approving in the first round (finding open) deploys with the goal lost: hazard at 1 misselection, none at 0.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| revise |  | Benign | intended while a finding is open; after the Author addressed it a further round is a detour (approve is still reachable and safe) |
| approve | findings_addressed | Benign | intended: all reviews pass once the findings are addressed |
| approve | not findings_addressed | Catastrophic | the Merger approves with a review still rejecting: `deploy` fires and the goal is lost |
