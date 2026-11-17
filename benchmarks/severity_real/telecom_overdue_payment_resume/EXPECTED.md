# EXPECTED: telecom_overdue_payment_resume

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
- PNR: make_payment
- static choice points: 2 agent, 3 external
- irreversible tools: make_payment (declared)
- bystander: every act is the first node of its branch or follows a message addressed to its owner (or an act of the same role): expected 0 pairs, exact.

Why k* = 0: with 0 misselections a payment request is sent only for an overdue bill, so the user's payment (or decline) always leaves the goal reachable. One wrong `send_request` for a bill that is not overdue (the tool does not check) lets the user accept and pay it, with the goal lost.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| send_request | bill_overdue | Benign | intended: the bill is overdue (L105) |
| send_request |  | Catastrophic | bill not overdue: the tool does not check (L117), the user may accept and pay it; payment is final and the goal is lost |
| no_request | bill_not_overdue | Benign | intended: nothing to collect |
| no_request |  | Futile | withholds the request for an overdue bill: no payment or decline, goal lost |
| resume | contract_ok | Benign | intended: bills paid and the contract is valid (L125) |
| resume |  | Futile | lifts a suspension the policy forbids (L126): goal lost; `resume_line` is not irreversible, so no hazard |
| refuse_resume | contract_ended | Benign | intended: L126 |
| refuse_resume |  | Futile | refuses to lift an allowed suspension: goal lost |
