# Provenance: retail_return_delivered_order

Ported from tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18): `_sources/tau-bench/retail/wiki.md` and
`_sources/tau-bench/retail/tools/return_delivered_order_items.py`. Read as text only.

## What comes from where

* Authentication gate (`proceed_auth` guard `auth_ok` / `deny_auth` guard `auth_failed`; external (System)
  `user_located` / `user_not_located`): `wiki.md` L5 "At the beginning of the conversation, you have to
  authenticate the user identity by locating their user id via email, or via name + zip code. This has to be
  done even when the user already provides the user id."; L9 "You can only help one user per conversation ...
  and must deny any requests for tasks related to any other user." No retail tool checks authentication, so
  this gate is a guard only.
* Status gate (external (System) `delivered` (`status_delivered`) / `not_delivered` (`status_other`); agent
  `proceed_status` guard `status_delivered` / `deny_status` guard `status_other`): L65 "An order can only be
  returned if its status is 'delivered', and you should check its status before taking the action."
* Refund destination gate (external (User) `original_method_or_gift_card` (`dest_ok`) / `other_destination`
  (`dest_bad`); agent `proceed_destination` guard `dest_ok` / `ask_other_destination` guard `dest_bad`): L69
  "The refund must either go to the original payment method, or an existing gift card."; L67 "The user needs to
  confirm the order id, the list of items to be returned, and a payment method to receive the refund."
* Confirmation: message `ListDetailsAndAskConfirmation`, external (User) `yes` / `not_yes`, agent `execute` /
  `hold`: L11 (explicit yes for "return"); L71 "After user confirmation, the order status will be changed to
  'return requested', and the user will receive an email regarding how to return items."
* Capability `return_delivered_order_items`: the action definition.

Goal: authenticated, delivered, valid destination and (return requested and confirmed, or not confirmed and not
requested); or a rule fails and not requested.

## Tool-side checks (`pre = status_delivered and dest_ok`)

`return_delivered_order_items.py` returns "Error: non-delivered order cannot be returned" (L19), "payment method
not found" (L24) and "payment method should be either the original payment method or a gift card" (L29): both
policy conditions are enforced. Authentication is not.

## Irreversible

`return_delivered_order_items` is declared irreversible. Policy: L71 (status becomes 'return requested' and the
user is emailed how to return the items); the exchange tool's description states the shared rule: "For a
delivered order, return or exchange can be only done once by the agent." (`exchange_delivered_order_items.py`
L83). No tool reverses a return request. No delete-list.

## Policy silent / not modelled

* The list of items and the order id are values no guard reads.
* Items already returned or an unknown item are tool errors, not policy conditions: not modelled.

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
