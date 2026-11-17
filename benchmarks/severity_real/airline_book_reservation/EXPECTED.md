# EXPECTED: airline_book_reservation

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
- PNR: book_reservation
- static choice points: 3 agent, 3 external
- irreversible tools: book_reservation (declared)
- bystander: every act is the first node of its branch or follows a message addressed to its owner (or an act of the same role): expected 0 pairs, exact.

Why k* = 0: with 0 misselections the agent proceeds only with at most five passengers and a valid payment plan, and books only after a yes. One wrong `book_reservation` after a `not_yes` charges the payment methods (and burns a certificate) with the goal lost.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| proceed_passengers | pax_ok | Benign | intended: at most five passengers (L32) |
| proceed_passengers |  | Catastrophic | more than five passengers: the tool does not count, a later `execute` with a valid plan fires and the goal is lost |
| deny_passengers | pax_bad | Benign | intended: L32 |
| deny_passengers |  | Futile | denies an allowed booking: goal lost, nothing irreversible |
| proceed_payment | pay_ok | Benign | intended: a valid plan |
| proceed_payment | pay_bad_tool | Benign | a payment method not in the profile: the tool blocks the booking, the agent can still hold; goal reachable |
| proceed_payment |  | Catastrophic | too many methods of one kind: the tool does not check it, a later `execute` fires and the goal is lost |
| ask_other_payment | pay_bad_rule or pay_bad_tool | Benign | intended: the agent asks for a valid plan (L34) |
| ask_other_payment | pax_bad | Benign | needless ask, but the passenger rule already fails so the goal (no booking) is reachable |
| ask_other_payment |  | Futile | needless ask on an allowed booking with a valid plan: no booking, goal lost |
| execute | pax_ok and pay_ok and confirmed | Benign | intended: rules hold, user said yes |
| execute | pay_bad_tool | Futile | blocked by the tool (payment method not usable): nothing fires, goal lost |
| execute |  | Catastrophic | the tool accepts the booking although a rule fails or the user did not say yes: goal lost |
| hold | pax_ok and pay_ok and confirmed | Futile | refuses an allowed, confirmed booking: goal lost |
| hold |  | Benign | intended: a rule fails or no yes |
