# Provenance: airline_change_cabin

Ported from tau2-bench `c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4` (2026-11-10): `_sources/tau2-bench/airline/policy.md`. Read as text only. The tau2-bench airline
tool code was not vendored (only the policy), so the pack has no tool-side `pre`.

## What comes from where

| Element | Source (`policy.md`) |
|---|---|
| external (System): `some_flight_flown` (`flown_flight`) / `none_flown` | L116 "Cabin cannot be changed if any flight in the reservation has already been flown." |
| agent choice 1: `proceed_status` (guard `none_flown`) / `deny_status` (guard `flown_flight`) | L116; L13 "You should deny user requests that are against this policy." |
| external (User): `whole_reservation` / `one_segment_only` | L118 "Cabin class must remain the same across all the flights in the same reservation; changing cabin for just one flight segment is not possible." |
| agent choice 2: `proceed_scope` (guard `whole_reservation`) / `deny_scope` (guard `one_segment`) | L118; L13 |
| message `ListDetailsAndAskConfirmation`, external (User) `yes` / `not_yes` | L7 "(booking, modifying flights, editing baggage, changing cabin class, or updating passenger information), you must list the action details and obtain explicit user confirmation (yes) to proceed." |
| agent choice 3: `execute` / `hold` | L7; guard of `execute`: both rules hold and the user said yes |
| capability `change_cabin` | the policy names no tool; the name is mine |

Goal: both rules hold and (changed and confirmed, or not confirmed and not changed), or a rule fails and not
changed.

## Irreversible

`change_cabin` is declared irreversible. Policy: L119 "If the price after cabin change is higher than the
original price, the user is required to pay for the difference." and L120 "If the price after cabin change is
lower than the original price, the user is should be refunded the difference." (money moves in both
directions). That a cabin change cannot be undone by the agent is my judgement; the policy does not say final.

## Policy silent / not modelled

* The first sentence of L117, "In other cases, all reservations, including basic economy, can change cabin
  without changing the flights", is the complement of the flown rule; no separate choice.
* The direction of the price difference (L119-120) is a system fact no guard reads: not modelled.
* No tool-side check is known, so both rules are guards only (tau2 tool code not vendored).

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
