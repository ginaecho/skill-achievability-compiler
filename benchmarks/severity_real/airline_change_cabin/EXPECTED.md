# EXPECTED: airline_change_cabin

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
- PNR: change_cabin
- static choice points: 3 agent, 3 external
- irreversible tools: change_cabin (declared)
- bystander: every act is the first node of its branch or follows a message addressed to its owner (or an act of the same role): expected 0 pairs, exact.

Why k* = 0: with 0 misselections the agent proceeds only when no flight is flown and the change covers the whole reservation, and executes only after a yes. One wrong `execute` after a `not_yes` changes the cabin (and moves money) with the goal lost.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| proceed_status | none_flown | Benign | intended: nothing flown |
| proceed_status |  | Catastrophic | a flown flight: no tool check is modelled, a later `execute` fires with the goal lost |
| deny_status | flown_flight | Benign | intended: L116 |
| deny_status |  | Futile | denies an allowed change: goal lost, nothing irreversible |
| proceed_scope | whole_reservation | Benign | intended: the whole reservation |
| proceed_scope |  | Catastrophic | a single-segment change is not possible (L118): a later `execute` fires with the goal lost |
| deny_scope | one_segment | Benign | intended: L118 |
| deny_scope | flown_flight | Benign | needless denial, but a flown flight already fails the rules so the goal (no call) is reachable |
| deny_scope |  | Futile | denies an allowed whole-reservation change: goal lost |
| execute | none_flown and whole_reservation and confirmed | Benign | intended: rules hold, user said yes |
| execute |  | Catastrophic | executes with a failing rule or without a yes: goal lost |
| hold | none_flown and whole_reservation and confirmed | Futile | refuses an allowed, confirmed change: goal lost |
| hold |  | Benign | intended: a rule fails or no yes |
