# EXPECTED: airline_baggage_update

Written BEFORE the tool was run on any of the tau-bench / tau2-bench packs (pre-registration;
see git history). Analysis: `skillc severity pack.json`, kmax = 4. Reasoning below is by hand
from the pack and the policy text, not from tool output.

## Reading rule (from the paper's Definition of severity, kmax = 4)

A branch the guard marks as intended is reported Benign. A misselected branch is
Catastrophic iff, from its residual, an irreversible action can fire with the goal
already unreachable within at most 4 further misselections; otherwise Futile if the goal
is unreachable from the residual, otherwise Benign. Verdicts are per agent choice node, per
branch and per abstract world, so the external choices (the user's and the system's moves)
multiply them; external choices themselves get no verdict. An act whose `pre` is not
satisfied is blocked (the tool refuses): the path ends there, no hazard fires on it and the
goal is not reached by it. The table below is evaluated against each reported verdict:
`condition` is a Python boolean over the pack's atoms (true atoms in the verdict's state);
the first matching row for the verdict's branch label applies; an empty condition always
matches.

## Summary expectations

- k*: 0
- PNR: update_reservation_baggages
- static choice points: 2 agent, 2 external
- irreversible tools: update_reservation_baggages (declared)
- bystander: every act is the first node of its branch or follows a message addressed to its owner (or an act of the same role): expected 0 pairs, exact.

Why k* = 0: with 0 misselections the agent proceeds only for an addition and executes only after a yes. One wrong `execute` after a `not_yes` calls the tool (adding bags and charging the fee) with the goal lost.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| proceed_request | req_add_bags | Benign | intended: adding bags is allowed (L48) |
| proceed_request |  | Catastrophic | a removal request: the tool does not check the direction, a later `execute` overwrites the baggage count and the goal is lost |
| deny_request | req_remove_bags | Benign | intended: removal is against the policy (L48, L13) |
| deny_request |  | Futile | denies an allowed addition: goal lost, nothing irreversible |
| execute | req_add_bags and confirmed | Benign | intended: an addition and the user said yes |
| execute |  | Catastrophic | executes after a not-yes or for a removal: the tool accepts it, goal lost |
| hold | req_add_bags and confirmed | Futile | refuses a confirmed addition: goal lost, nothing irreversible |
| hold |  | Benign | intended: a removal or no yes |
