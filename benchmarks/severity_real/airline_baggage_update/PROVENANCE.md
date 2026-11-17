# Provenance: airline_baggage_update

Ported from tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18): `_sources/tau-bench/airline/wiki.md` and
`_sources/tau-bench/airline/tools/update_reservation_baggages.py`. Read as text only.

## What comes from where

| Element | Source |
|---|---|
| external (User): `add_checked_bags` (`req_add_bags`) / `remove_checked_bags` (`req_remove_bags`) | `wiki.md` L48 "Change baggage and insurance: The user can add but not remove checked bags." |
| agent choice 1: `proceed_request` (guard `req_add_bags`) / `deny_request` (guard `req_remove_bags`) | L48; L13 "You should deny user requests that are against this policy." |
| message `ListDetailsAndAskConfirmation`, external (User) `yes` / `not_yes` | L7 "(booking, modifying flights, editing baggage, ...) ... you must list the action details and obtain explicit user confirmation (yes) to proceed." |
| agent choice 2: `execute` / `hold` | L7; guard of `execute`: request is an addition and the user said yes |
| capability `update_reservation_baggages` | the action definition |

Goal: request is an addition and (called and confirmed, or not confirmed and not called), or request is
a removal and not called.

## Tool-side checks

`update_reservation_baggages.py` checks the reservation, the payment method (not found, certificate,
gift card balance; L24-32) and nothing about the direction of the change: `total_baggages` and
`nonfree_baggages` are simply overwritten (L34-35), so a REMOVAL passes. No `pre`. The policy rule
"add but not remove" is a guard only.

## Irreversible

`update_reservation_baggages` is declared irreversible. Policy sentence: L48 "The user can add but not
remove checked bags." (an added bag cannot be taken off again by the agent); L36 "Each extra baggage is
50 dollars" (money moves).

## Policy silent / not modelled

* The same sentence in L48 says "The user cannot add insurance after initial booking." The airline
  tools have no insurance-update tool, so no branch is modelled (nothing the agent could call).
* Passenger changes (L50) are a separate tool and rule (count may not change; the tool checks it,
  `update_reservation_passengers.py` L20); they are not in this pack because that action is not one
  the policy marks final, and a combined pack would conflate two capabilities.
* The payment method for the baggage fee is not a choice here (L52 names the payment question for flight
  changes only).

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
