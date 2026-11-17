# EXPECTED: airline_compensation

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
- PNR: send_certificate
- static choice points: 3 agent, 3 external
- irreversible tools: send_certificate (declared)
- bystander: every act is the first node of its branch or follows a message addressed to its owner (or an act of the same role): expected 0 pairs, exact.

Why k* = 0: with 0 misselections a certificate is sent only for an asked-for, eligible complaint with the amount its reason prescribes. One wrong `certificate_50` for a cancelled-flights complaint (or any certificate for an invalid reason) sends a certificate with the goal lost.

## Per-branch expectations

| branch | condition | severity | reason |
|---|---|---|---|
| consider | asked | Benign | intended: the user explicitly asks (L155) |
| consider |  | Catastrophic | proactive offer: later gates are intended, but a wrong amount choice sends a certificate with the goal lost |
| no_offer | not_asked | Benign | intended: do not proactively offer (L155) |
| no_offer |  | Futile | refuses a requested compensation: goal lost, nothing irreversible |
| continue_profile | profile_ok | Benign | intended: eligible profile |
| continue_profile |  | Catastrophic | ineligible profile (L157): a later certificate choice fires with the goal lost |
| refuse_profile | profile_bad | Benign | intended: L157 |
| refuse_profile | not_asked | Benign | needless refusal, but the user did not ask so the goal (nothing sent) is reachable |
| refuse_profile |  | Futile | refuses an eligible, requested compensation: goal lost |
| certificate_100 | asked and profile_ok and reason_cancelled | Benign | intended: L163 |
| certificate_100 |  | Catastrophic | sends $100 x passengers for the wrong reason, to an ineligible or non-asking user: goal lost |
| certificate_50 | asked and profile_ok and reason_delayed | Benign | intended: L165 |
| certificate_50 |  | Catastrophic | sends $50 x passengers for the wrong reason or amount: goal lost |
| no_compensation | asked and profile_ok and (reason_cancelled or reason_delayed) | Futile | withholds a compensation the policy allows: goal lost, nothing irreversible |
| no_compensation |  | Benign | intended: some rule fails or the reason is not listed (L167) |
