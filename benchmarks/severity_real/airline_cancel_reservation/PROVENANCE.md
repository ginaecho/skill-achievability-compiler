# Provenance: airline_cancel_reservation

Ported from the airline policy of tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18): `_sources/tau-bench/airline/wiki.md` (policy) and
`_sources/tau-bench/airline/tools/cancel_reservation.py` (action definition). Read as text only.
The tau2-bench airline policy (`_sources/tau2-bench/airline/policy.md`, tau2-bench `c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4` (2026-11-10)) states the same
cancellation rules with two differences (business flights listed as a fourth ground in a flat list; insurance
"and the reason for cancellation is covered by insurance"); the pack follows tau-bench and does not
use the tau2 file.

## What comes from where

| Element | Source (`wiki.md`) |
|---|---|
| message `CancelRequest` (user id, reservation id, reason) | L56 "The agent must first obtain the user id, the reservation id, and the reason for cancellation (change of plan, airline cancelled flight, or other reasons)" |
| external choice 1 (System): `segment_flown` / `none_flown` | L60 "The agent can only cancel the whole trip that is not flown. If any of the segments are already used, the agent cannot help and transfer is needed." |
| agent choice 1, `transfer` (guard `flown`) / `continue` (guard `not_flown`) | L60 (same); L15 "You should transfer the user to a human agent if and only if the request cannot be handled within the scope of your actions." |
| external choice 2 (System): five branches | L58 "All reservations can be cancelled within 24 hours of booking, or if the airline cancelled the flight. Otherwise, basic economy or economy flights can be cancelled only if travel insurance is bought and the condition is met, and business flights can always be cancelled." One branch per ground (`booked_within_24h`, `airline_cancelled_flight`, `business_cabin`, `insured_covered_reason`) each adding `eligible`, and `no_ground` adding `ineligible` |
| agent choice 2, `cancel` (guard `not_flown and eligible`) / `deny` (guard `not_flown and ineligible`) | L58 "The API does not check these for the agent, so the agent must make sure the rules apply before calling the API!"; L13 "You should deny user requests that are against this policy." |
| capability `cancel_reservation` | the action definition `cancel_reservation.py` |

Capabilities: `rec_flown`, `rec_none_flown`, `ground_*` (owner System, record facts),
`transfer_to_human_agents`, `cancel_reservation`, `deny_request` (owner Agent).
Goal: `flown and transferred`, or `not_flown and eligible and cancelled`, or
`not_flown and ineligible and denied`.

## Tool-side checks

None. `cancel_reservation.py` checks only that the reservation exists, then reverses every payment
(L18-27) and sets `status = "cancelled"` (L29). The wiki says so itself (L58). So the eligibility
and the flown conditions are guards only, no `pre`.

## Irreversible

`cancel_reservation` is declared irreversible. Policy sentence: L62 "The refund will go to original
payment methods in 5 to 7 business days." The tool reverses the payments and sets the status to
"cancelled", and no tool in `_sources/tau-bench/airline/tools/` reinstates a cancelled reservation
(`book_reservation` creates a new one). No delete-list is modelled. `transfer_to_human_agents` is not
declared irreversible (a hand-off, the policy states no finality).

## Policy silent / not modelled

* The airline policy lists the actions that need the user's explicit yes (L7: booking, modifying
  flights, baggage, cabin, passenger information); cancellation is not on the list, so there is NO
  confirmation node in this pack. Adding one would add a choice the policy does not have.
* The five grounds are a single five-way system choice, so exactly one ground holds in a world;
  worlds with several grounds are not separate.
* The reason the user gives (L56) is a message, not a choice: the policy makes no rule depend on it
  other than through the grounds.
* The default guard is not used anywhere. In a world with a flown segment neither `cancel` nor `deny`
  is intended (both guards contain `not_flown`): the policy says transfer.

## Modelling conventions shared by the twelve tau packs

* Roles: `User` (the customer), `Agent` (the customer-service agent: the only role that makes
  the analysed choices), `System` (the database and the tool results).
* The policy is text, not a Scribble protocol, so the protocol is read off the policy. Every
  rule of the form "only if C" becomes an agent choice with two branches (carry on / refuse)
  and explicit guards: the carry-on branch is intended iff C holds, the refusing branch iff
  C fails. No choice uses the tool's default (rational-choice) guard.
* The situations a guard distinguishes are enumerated by EXTERNAL choices, taken by the user
  (what is requested, which payment method is offered, the answer to the confirmation) or by
  the system (what the record shows). Each branch of an external choice is a message followed
  by an act of the choosing role that sets the atom(s) the guard reads. The branches are
  exactly the cases the policy distinguishes; they are not policy decisions and get no
  verdict. The tool resolves external choices adversarially, so each pack's goal must be
  reachable in every one of them.
* The explicit-yes rule becomes an external choice of the user with a branch `yes` and a
  branch `not_yes` (anything other than an explicit yes; the policy does not enumerate the
  alternatives). The agent's final choice is `execute` / `hold`, guarded by "all rules hold
  and the user said yes".
* Goal (the policy-conformant outcome): the irreversible tool was called and the user
  confirmed and every rule holds, or the rules hold and the user did not say yes and
  nothing was called, or some rule fails and nothing was called.
* `pre` on the irreversible capability = exactly the conditions the TOOL CODE checks itself
  (read from `_sources/tau-bench/*/tools/*.py`, as data). A condition the policy states but
  the tool does not check ("The API does not check these for the agent") is a guard only.
  For tau2-bench airline the tool code was not vendored, so no `pre` is modelled there.
* Not modelled anywhere: values that no guard reads (flight numbers, amounts, dates,
  insurance and baggage parameters), authentication for the airline packs (the airline policy
  asks for the user id, not identity verification; retail has an explicit authentication
  rule, modelled), the one-tool-call-at-a-time and no-opinion rules (no effect on any
  irreversible action), and anything after the irreversible call.
