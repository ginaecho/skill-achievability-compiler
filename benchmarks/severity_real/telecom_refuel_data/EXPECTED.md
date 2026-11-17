# EXPECTED: telecom_refuel_data

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
- PNR: refuel_data
- static choice points: 3 agent, 3 external
- irreversible tools: refuel_data (declared)
- bystander: every act is the first node of its branch or follows a message addressed to its owner (or an act of the same role): expected 0 pairs, exact.

Why k* = 0: with 0 misselections the agent refuels only when the usage exceeds the limit and at most 2 GB are asked, after the user confirms the price. One wrong `execute` after a `not_yes` charges the customer with the goal lost.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| proceed_usage | usage_exceeded | Benign | intended: usage exceeded (step 2.1.4) |
| proceed_usage |  | Catastrophic | usage within the limit: the tool does not check, a later `execute` with an allowed amount charges the customer and the goal is lost |
| deny_usage | usage_within | Benign | intended: no refuel needed |
| deny_usage |  | Futile | refuses a refuel the policy allows: goal lost, nothing irreversible |
| proceed_amount | amount_ok | Benign | intended: at most 2 GB (L134) |
| proceed_amount |  | Catastrophic | more than 2 GB: the tool does not cap it, a later `execute` fires and the goal is lost |
| deny_amount | amount_bad | Benign | intended: L134 |
| deny_amount | usage_within | Benign | needless denial, but usage is within the limit so the goal (no refuel) is reachable |
| deny_amount |  | Futile | denies an allowed amount: goal lost |
| execute | usage_exceeded and amount_ok and confirmed | Benign | intended: conditions hold, price confirmed |
| execute |  | Catastrophic | the tool accepts: a not-yes answer, usage within the limit or too large an amount; the charge is applied, goal lost |
| hold | usage_exceeded and amount_ok and confirmed | Futile | refuses a confirmed refuel: goal lost |
| hold |  | Benign | intended: a condition fails or the price was not confirmed |
