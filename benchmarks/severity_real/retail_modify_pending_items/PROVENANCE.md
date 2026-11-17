# Provenance: retail_modify_pending_items

Ported from tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18): `_sources/tau-bench/retail/wiki.md` and
`_sources/tau-bench/retail/tools/modify_pending_order_items.py`. Read as text only.

## What comes from where

* Authentication gate (`proceed_auth` guard `auth_ok` / `deny_auth` guard `auth_failed`; external (System)
  `user_located` / `user_not_located`): `wiki.md` L5 "At the beginning of the conversation, you have to
  authenticate the user identity by locating their user id via email, or via name + zip code. This has to be
  done even when the user already provides the user id."; L9 "You can only help one user per conversation ...
  and must deny any requests for tasks related to any other user." No retail tool checks authentication, so
  this gate is a guard only.
* Status gate (external (System) `pending` / `not_pending`; agent `proceed_status` guard `status_pending` /
  `deny_status` guard `status_other`): L43 "An order can only be modified if its status is 'pending', and you
  should check its status before taking the action."
* Items gate (external (User) `same_product_other_option` (`items_ok`) / `different_product_type`
  (`items_bad`); agent `proceed_items` guard `items_ok` / `deny_items` guard `items_bad`): L59 "each item can be
  modified to an available new item of the same product but of different product option. There cannot be any
  change of product types, e.g. modify shirt to shoe."
* Payment gate (external (User) `payment_covers` (`pay_ok`) / `gift_card_short` (`pay_bad`); agent
  `proceed_payment` guard `pay_ok` / `ask_other_payment` guard `pay_bad`): L61 "The user must provide a payment
  method to pay or receive refund of the price difference. If the user provides a gift card, it must have
  enough balance to cover the price difference."
* Confirmation and completeness: message `ListDetailsAndAskConfirmation`, external (User) `yes_all_items_given`
  (`confirmed`) / `more_items_to_add` (`more_items`) / `not_yes` (`declined`); agent `execute` / `hold`: L11
  (explicit yes for "modify"); L57 "In particular, remember to remind the customer to confirm they have provided
  all items to be modified."; L31 "Exchange or modify order tools can only be called once. Be sure that all items
  to be changed are collected into a list before making the tool call!!!"
* Capability `modify_pending_order_items`: the action definition.

Goal: authenticated, pending, same-product items, payment covers, and (modified and confirmed, or not modified
and (declined or more items to add)); or a rule fails and not modified.

## Tool-side checks (`pre = status_pending and items_ok and pay_ok`)

`modify_pending_order_items.py` returns an error for a non-pending order (L23), for a new item that is not an
available variant of the same product (L44: `new_item_id in products[product_id]["variants"]`), for an unknown
payment method (L52) and for a gift card whose balance is below the difference (L60). All three rules are
enforced by the tool. Authentication and the completeness of the item list are not checked.

## Irreversible

`modify_pending_order_items` is declared irreversible. Policy sentence, L57: "This action can only be called
once, and will change the order status to 'pending (items modifed)', and the agent will not be able to modify
or cancel the order anymore." The tool sets `status = "pending (item modified)"` (L84) so every later call fails
the pending check (L23). Money moves: the price difference is paid or refunded (L62-69). No delete-list.

## Policy silent / not modelled

* The `more_items_to_add` branch stands for "the user has not yet given all items"; the policy asks for the
  reminder and then the user's answer; the later collection of the missing items is not modelled (the pack
  ends with `hold`).
* The item identifiers and the price difference are not modelled.

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
