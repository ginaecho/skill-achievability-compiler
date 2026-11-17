# Provenance: airline_book_reservation

Ported from tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18): `_sources/tau-bench/airline/wiki.md` and
`_sources/tau-bench/airline/tools/book_reservation.py`. Read as text only.

## What comes from where

| Element | Source |
|---|---|
| message `BookingRequest` | `wiki.md` L30 "The agent must first obtain the user id, then ask for the trip type, origin, destination." |
| external (User): `at_most_five` (`pax_ok`) / `more_than_five` (`pax_bad`) | L32 "Each reservation can have at most five passengers." |
| agent choice 1: `proceed_passengers` (guard `pax_ok`) / `deny_passengers` (guard `pax_bad`) | L32; L13 deny |
| external (User): `valid_plan` (`pay_ok`) / `composition_violated` (`pay_bad_rule`) / `not_in_profile_or_short` (`pay_bad_tool`) | L34 "each reservation can use at most one travel certificate, at most one credit card, and at most three gift cards. ... All payment methods must already be in user profile for safety reasons." |
| agent choice 2: `proceed_payment` (guard `pay_ok`) / `ask_other_payment` (guard `pay_bad_rule or pay_bad_tool`) | L34 |
| message `ListDetailsAndAskConfirmation`, external (User) `yes` / `not_yes` | L7 "(booking, ...) you must list the action details and obtain explicit user confirmation (yes) to proceed." |
| agent choice 3: `execute` / `hold` | L7; guard of `execute`: passengers ok, payment ok, user said yes |
| capability `book_reservation` | the action definition |

Goal: passengers and payment ok and (booked and confirmed, or not confirmed and not booked), or a rule
fails and not booked.

## Tool-side checks (`pre = not pay_bad_tool`)

`book_reservation.py` returns an error for a payment method not in the profile (L82 "payment method ... not found") and for insufficient balance of a gift card or certificate (L89), and when the amounts do
not add up (L91). It does NOT count passengers and does NOT count payment methods per kind. So `pay_bad_tool`
(not in profile or short) is blocked by the tool: `pre = not pay_bad_tool`; `pax_bad` and
`pay_bad_rule` are guards only.

## Irreversible

`book_reservation` is declared irreversible. Policy sentence: L34 "The remaining amount of a travel
certificate is not refundable." The tool deletes a used certificate outright
(`del user["payment_methods"][payment_id]`, L100) and deducts gift cards; it creates a reservation and
charges the payment methods. No delete-list is modelled (the certificate loss is an effect of the same
call).

## Policy silent / not modelled

* Insurance (L38: "the agent should ask if the user wants to buy the travel insurance") and the baggage
  allowance (L36) are parameters of the booking; no guard reads them, so they are not modelled and the
  "ask about insurance" step is not a choice node.
* "Do not add checked bags that the user does not need" is in the tau2 policy only.
* Whether the user's plan with several methods adds up is the tool's check ("payment amount does not add
  up"), folded into `not_in_profile_or_short`.

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
