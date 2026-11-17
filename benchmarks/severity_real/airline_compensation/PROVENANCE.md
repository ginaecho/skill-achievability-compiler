# Provenance: airline_compensation

Ported from tau2-bench `c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4` (2026-11-10): `_sources/tau2-bench/airline/policy.md` (section "Refunds and Compensation", L154-167)
and, for the action, `_sources/tau-bench/airline/tools/send_certificate.py` (tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18), same domain, older
repository). Read as text only.

## What comes from where

| Element | Source (`policy.md`) |
|---|---|
| message `Complaint`; external (User): `asks_for_compensation` (`asked`) / `does_not_ask` (`not_asked`) | L155 "Do not proactively offer a compensation unless the user explicitly asks for one." |
| agent choice 1: `consider` (guard `asked`) / `no_offer` (guard `not_asked`) | L155 |
| external (System): `eligible_profile` (`profile_ok`) / `ineligible_profile` (`profile_bad`) | L157 "Do not compensate if the user is regular member and has no travel insurance and flies (basic) economy."; L161 "Only compensate if the user is a silver/gold member or has travel insurance or flies business." |
| agent choice 2: `continue_profile` (guard `profile_ok`) / `refuse_profile` (guard `profile_bad`) | L157, L161 |
| external (System): `cancelled_flights` / `delayed_wants_change_or_cancel` / `other_reason` | L163 "If the user complains about cancelled flights in a reservation, the agent can offer a certificate as a gesture after confirming the facts, with the amount being $100 times the number of passengers."; L165 "If the user complains about delayed flights in a reservation and wants to change or cancel the reservation, the agent can offer a certificate ... with the amount being $50 times the number of passengers."; L167 "Do not offer compensation for any other reason than the ones listed above." |
| agent choice 3: `certificate_100` (guard `asked and profile_ok and reason_cancelled`) / `certificate_50` (guard `asked and profile_ok and reason_delayed`) / `no_compensation` (guard: not (asked and profile_ok and (cancelled or delayed))) | L163, L165, L167 |
| capabilities `quote_100` / `quote_50` (add `amt_100` / `amt_50`) then `send_certificate` | the amount rule of L163 / L165 as an act, so that one irreversible capability serves both amounts; `send_certificate.py` ("Send a certificate to a user. Be careful!") |

Goal: asked, profile ok, cancelled flights, amount 100 and certificate sent; or asked, profile ok, delayed,
amount 50 and sent; or (not asked, or profile bad, or other reason) and not sent.

## Tool-side checks

None: `send_certificate.py` adds a certificate to the user for any amount (it checks only that the user
exists). All conditions are guards only. (The tau2 tool code was not vendored; the tau-bench one is the same
domain.)

## Irreversible

`send_certificate` is declared irreversible. The tool's own description says "Send a certificate to a
user. Be careful!"; a certificate is stored value in the user's payment methods and no tool in the airline
tool set withdraws it. L159 "Always confirms the facts before offering compensation." is a step, not a
choice.

## Policy silent / not modelled

* The airline policy has NO explicit-yes rule for compensation (L7 lists booking, flight changes, baggage,
  cabin and passenger updates), so there is no confirmation node; "confirms the facts" (L159) is about the
  complaint, not the user's consent.
* For delayed flights the certificate comes "after confirming the facts and changing or cancelling the
  reservation" (tau-bench L68, tau2 L165): the ordering after the change is not modelled (the change is its
  own protocol); the branch records only that the user wants a change or cancellation.
* The profile is one two-way system choice (silver/gold, insurance, business collapsed into `profile_ok`).
* The amounts are not numbers: `amt_100` / `amt_50` are atoms standing for "$100 / $50 times the number of
  passengers".

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
