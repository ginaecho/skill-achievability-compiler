# EXPECTED: retail_exchange_delivered_order

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
- PNR: exchange_delivered_order_items
- static choice points: 5 agent, 5 external
- irreversible tools: exchange_delivered_order_items (declared)
- bystander: every act is the first node of its branch or follows a message addressed to its owner (or an act of the same role): expected 0 pairs, exact.

Why k* = 0: with 0 misselections the agent requests the exchange only for an authenticated, delivered order with same-product items and a covering payment, after a yes that confirms all items are given. One wrong `execute` after a `not_yes` or a `more_items_to_add` answer requests the exchange, which the tool accepts and which can be done only once: the goal is lost.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| proceed_auth | auth_ok | Benign | intended: user located (L5) |
| proceed_auth |  | Catastrophic | unauthenticated user: no tool checks it, a later `execute` fires and the goal is lost |
| deny_auth | auth_failed | Benign | intended: L5, L9 |
| deny_auth |  | Futile | denies an authenticated user: goal lost |
| proceed_status | status_delivered | Benign | intended: delivered (L75) |
| proceed_status |  | Benign | non-delivered order: the tool refuses, the agent can still hold; goal reachable |
| deny_status | status_other | Benign | intended: L75 |
| deny_status | auth_failed | Benign | needless denial, but an earlier rule already fails so the goal (no call) is reachable |
| deny_status |  | Futile | denies an exchangeable order: goal lost |
| proceed_items | items_ok | Benign | intended: same product (L77) |
| proceed_items |  | Benign | a different product type: the tool refuses, the agent can still hold; goal reachable |
| deny_items | items_bad | Benign | intended: L77 |
| deny_items | auth_failed or status_other | Benign | needless denial, but an earlier rule already fails so the goal (no call) is reachable |
| deny_items |  | Futile | denies an allowed item change: goal lost |
| proceed_payment | pay_ok | Benign | intended: the payment method covers the difference (L79) |
| proceed_payment |  | Benign | gift card too small: the tool refuses, the agent can still hold; goal reachable |
| ask_other_payment | pay_bad | Benign | intended: L79 |
| ask_other_payment | auth_failed or status_other or items_bad | Benign | needless ask, but an earlier rule already fails so the goal (no call) is reachable |
| ask_other_payment |  | Futile | needless ask of a covering payment: no call made, goal lost |
| execute | auth_ok and status_delivered and items_ok and pay_ok and confirmed | Benign | intended: all rules hold, all items given, user said yes |
| execute | status_delivered and items_ok and pay_ok | Catastrophic | the tool accepts: unauthenticated user, a not-yes answer or items still to add; the exchange is requested once and for all, goal lost |
| execute |  | Futile | blocked by the tool (not delivered, wrong product, or gift card too small): nothing fires, goal lost |
| hold | auth_ok and status_delivered and items_ok and pay_ok and confirmed | Futile | refuses an allowed, confirmed exchange: goal lost |
| hold |  | Benign | intended: a rule fails, items remain to be added, or no yes |
