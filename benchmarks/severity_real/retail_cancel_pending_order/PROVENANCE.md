# Provenance: retail_cancel_pending_order

Ported from tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18): `_sources/tau-bench/retail/wiki.md` and
`_sources/tau-bench/retail/tools/cancel_pending_order.py`. Read as text only.

## What comes from where

* Authentication gate (`proceed_auth` guard `auth_ok` / `deny_auth` guard `auth_failed`; external (System)
  `user_located` / `user_not_located`): `wiki.md` L5 "At the beginning of the conversation, you have to
  authenticate the user identity by locating their user id via email, or via name + zip code. This has to be
  done even when the user already provides the user id."; L9 "You can only help one user per conversation ...
  and must deny any requests for tasks related to any other user." No retail tool checks authentication, so
  this gate is a guard only.
* Status gate (external (System) `pending` (`status_pending`) / `not_pending` (`status_other`); agent
  `proceed_status` guard `status_pending` / `deny_status` guard `status_other`): L35 "An order can only be
  cancelled if its status is 'pending', and you should check its status before taking the action."; L29 "Each
  order can be in status 'pending', 'processed', 'delivered', or 'cancelled'. Generally, you can only take
  action on pending or delivered orders."
* Reason gate (external (User) `no_longer_needed` / `ordered_by_mistake` (`reason_ok`) / `other_reason`
  (`reason_invalid`); agent `proceed_reason` guard `reason_ok` / `ask_valid_reason` guard `reason_invalid`):
  L37 "The user needs to confirm the order id and the reason (either 'no longer needed' or 'ordered by
  mistake') for cancellation."
* Confirmation: message `ListDetailsAndAskConfirmation`, external (User) `yes` / `not_yes`, agent
  `execute` / `hold`: L11 "Before taking consequential actions that update the database (cancel, modify,
  return, exchange), you have to list the action detail and obtain explicit user confirmation (yes) to
  proceed."; L39 "After user confirmation, the order status will be changed to 'cancelled'".
* Capability `cancel_pending_order`: the action definition.

Goal: authenticated, pending, valid reason and (cancelled and confirmed, or not confirmed and not
cancelled); or a rule fails and not cancelled.

## Tool-side checks (`pre = status_pending and reason_ok`)

`cancel_pending_order.py` returns "Error: non-pending order cannot be cancelled" (L16) and "Error: invalid
reason" (L21). Both policy conditions are enforced by the tool: `pre = status_pending and reason_ok`.
Authentication is not checked by the tool.

## Irreversible

`cancel_pending_order` is declared irreversible. Policy sentences: L39 "After user confirmation, the order
status will be changed to 'cancelled', and the total will be refunded via the original payment method
immediately if it is gift card, otherwise in 5 to 7 business days." and L29 (a cancelled order is not
pending or delivered, so no tool acts on it again; there is no un-cancel tool).

## Policy silent / not modelled

* Which order id, the payment methods refunded and their timing (no guard reads them).
* The reason `other_reason` is the tool's rejection set (anything but the two enum values); the agent
  response to it ("ask for a valid reason") is my reading of "needs to confirm ... either ... or".

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
