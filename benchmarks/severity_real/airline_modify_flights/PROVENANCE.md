# Provenance: airline_modify_flights

Ported from tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18): `_sources/tau-bench/airline/wiki.md` and
`_sources/tau-bench/airline/tools/update_reservation_flights.py`. Read as text only.

## What comes from where

| Element | Source (`wiki.md`) |
|---|---|
| message `ModifyFlightsRequest` | L42 "The agent must first obtain the user id and the reservation id." |
| external (System): `basic_economy` / `other_cabin` | L44 "Basic economy flights cannot be modified." |
| external (User): `route_unchanged` / `route_changed` | L44 "Other reservations can be modified without changing the origin, destination, and trip type." |
| agent choice 1: `proceed_rules` (guard `other_cabin and route_unchanged`) / `deny_rules` (guard `basic_economy or route_changed`) | L44 "The API does not check these for the agent, so the agent must make sure the rules apply before calling the API!"; L13 deny |
| message `AskPaymentMethod`, external (User): `gift_or_credit_card` (`pay_valid`) / `certificate_or_other` (`pay_invalid`) | L52 "If the flights are changed, the user needs to provide one gift card or credit card for payment or refund method. The agent should ask for the payment or refund method instead." |
| agent choice 2: `accept_method` (guard `pay_valid`) / `ask_other_method` (guard `pay_invalid`) | L52 (same) |
| message `ListDetailsAndAskConfirmation`, external (User): `yes` / `not_yes` | L7 "you must list the action details and obtain explicit user confirmation (yes) to proceed" (modifying flights is on the list) |
| agent choice 3: `execute` / `hold` | L7; guard of `execute`: all rules hold, payment valid, user said yes |
| capability `update_reservation_flights` | the action definition |

Goal: the three rules hold and (the tool was called and the user said yes, or the user did not say
yes and it was not called), or a rule fails and it was not called.

## Tool-side checks (`pre = pay_valid`)

`update_reservation_flights.py` rejects a payment method that is not in the profile (L66), a
certificate ("Error: certificate cannot be used to update reservation", L69) and a gift card with too
little balance (L74). So an invalid payment method is blocked by the tool: `pre = pay_valid`. It does
NOT check the cabin, nor the origin / destination / trip type; the wiki says it does not (L44). Those
two rules are guards only.

## Irreversible

`update_reservation_flights` is declared irreversible: it moves money and replaces the booked
flights (the tool deducts the price difference and rewrites `reservation["flights"]`). Policy: L52
"the user needs to provide one gift card or credit card for payment or refund method"; L44 "Some flight
segments can be kept, but their prices will not be updated based on the current price." No tool
undoes it except another call of the same tool. The judgement that a money-moving booking change is
final is mine.

## Policy silent / not modelled

* The payment choice uses the tool's own rejection set (certificate or unknown method) as the
  invalid branch; the policy text says only "one gift card or credit card".
* Insufficient gift-card balance is folded into `certificate_or_other`.
* Seat availability, price difference amounts, kept segments: no guard reads them.

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
