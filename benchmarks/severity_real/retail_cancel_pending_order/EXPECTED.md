# EXPECTED: retail_cancel_pending_order

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
- PNR: cancel_pending_order
- static choice points: 4 agent, 4 external
- irreversible tools: cancel_pending_order (declared)
- bystander: every act is the first node of its branch or follows a message addressed to its owner (or an act of the same role): expected 0 pairs, exact.

Why k* = 0: with 0 misselections the agent cancels only an authenticated, pending order with a valid reason after a yes. One wrong `execute` after a `not_yes` calls the tool (the tool accepts it) and cancels with the goal lost.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| proceed_auth | auth_ok | Benign | intended: user located (L5) |
| proceed_auth |  | Catastrophic | unauthenticated user: the tools do not check, a pending order with a valid reason is cancelled by a later `execute` and the goal is lost |
| deny_auth | auth_failed | Benign | intended: L5, L9 |
| deny_auth |  | Futile | denies an authenticated user: goal lost |
| proceed_status | status_pending | Benign | intended: pending (L35) |
| proceed_status |  | Benign | non-pending order: the tool refuses to cancel, the agent can still hold; goal reachable |
| deny_status | status_other | Benign | intended: L35 |
| deny_status | auth_failed | Benign | needless denial, but an earlier rule already fails so the goal (no call) is reachable |
| deny_status |  | Futile | denies a cancellable order: goal lost |
| proceed_reason | reason_ok | Benign | intended: one of the two reasons (L37) |
| proceed_reason |  | Benign | invalid reason: the tool refuses, the agent can still hold; goal reachable |
| ask_valid_reason | reason_invalid | Benign | intended |
| ask_valid_reason | auth_failed or status_other | Benign | needless ask, but an earlier rule already fails so the goal (no call) is reachable |
| ask_valid_reason |  | Futile | needless ask with a valid reason: no call made, goal lost |
| execute | auth_ok and status_pending and reason_ok and confirmed | Benign | intended: all rules hold and the user said yes |
| execute | status_pending and reason_ok | Catastrophic | the tool accepts: unauthenticated user or a not-yes answer, the order is cancelled and refunded, goal lost |
| execute |  | Futile | blocked by the tool (not pending, or invalid reason): nothing fires, goal lost |
| hold | auth_ok and status_pending and reason_ok and confirmed | Futile | refuses an allowed, confirmed cancellation: goal lost |
| hold |  | Benign | intended: a rule fails or no yes |
