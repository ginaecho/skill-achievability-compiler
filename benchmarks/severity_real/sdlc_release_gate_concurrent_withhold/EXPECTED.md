# EXPECTED: sdlc_release_gate_concurrent_withhold

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
- bystander: As sdlc_release_gate_concurrent, plus `withhold` after NoDeploy (addressed to DevOps): expected 0 pairs, exact.

Why k* = 0: As in sdlc_release_gate: approving in round one deploys with the finding open (1 misselection); `reject` alone never reaches an irreversible action.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| revise |  | Benign | intended while a finding is open; a detour afterwards |
| reject |  | Futile | not intended in a fixable world; NoDeploy/Withheld ends the run, nothing irreversible fires, the goal (deployed) is lost |
| approve | findings_addressed | Benign | intended |
| approve | not findings_addressed | Catastrophic | approve while a finding is open: `deploy` fires and the goal is lost |
