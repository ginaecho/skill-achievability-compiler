# Provenance: retail_exchange_delivered_order

Ported from tau-bench `59a200c6d575d595120f1cb70fea53cef0632f6b` (2026-03-18): `_sources/tau-bench/retail/wiki.md` and
`_sources/tau-bench/retail/tools/exchange_delivered_order_items.py`. Read as text only. Same choice structure as
`retail_modify_pending_items` (the two procedures share their rules about same-product items, payment for the
difference and "provided all items"); it is a separate protocol because the order status, the rule texts and the
tool differ, and its verdicts are not independent evidence of a different structure.

## What comes from where

* Authentication gate (`proceed_auth` guard `auth_ok` / `deny_auth` guard `auth_failed`; external (System)
  `user_located` / `user_not_located`): `wiki.md` L5 "At the beginning of the conversation, you have to
  authenticate the user identity by locating their user id via email, or via name + zip code. This has to be
  done even when the user already provides the user id."; L9 "You can only help one user per conversation ...
  and must deny any requests for tasks related to any other user." No retail tool checks authentication, so
  this gate is a guard only.
* Status gate (external (System) `delivered` (`status_delivered`) / `not_delivered` (`status_other`); agent
  `proceed_status` / `deny_status`): L75 "An order can only be exchanged if its status is 'delivered', and you
  should check its status before taking the action."
* Items gate (external (User) `same_product_other_option` (`items_ok`) / `different_product_type` (`items_bad`);
  agent `proceed_items` / `deny_items`): L77 "each item can be exchanged to an available new item of the same
  product but of different product option. There cannot be any change of product types, e.g. modify shirt to
  shoe."
* Payment gate (external (User) `payment_covers` (`pay_ok`) / `gift_card_short` (`pay_bad`); agent
  `proceed_payment` / `ask_other_payment`): L79 "The user must provide a payment method to pay or receive refund of
  the price difference. If the user provides a gift card, it must have enough balance to cover the price
  difference."
* Confirmation and completeness: external (User) `yes_all_items_given` / `more_items_to_add` / `not_yes`; agent
  `execute` / `hold`: L11 (explicit yes for "exchange"); L75 "In particular, remember to remind the customer to
  confirm they have provided all items to be exchanged."; L31 "Exchange or modify order tools can only be called
  once. Be sure that all items to be changed are collected into a list before making the tool call!!!"
* Capability `exchange_delivered_order_items`: the action definition.

Goal: authenticated, delivered, same-product items, payment covers, and (exchange requested and confirmed, or not
requested and (declined or more items to add)); or a rule fails and not requested.

## Tool-side checks (`pre = status_delivered and items_ok and pay_ok`)

`exchange_delivered_order_items.py` returns an error for a non-delivered order (L24), for a new item that is not an
available variant of the product (L45), for an unknown payment method (L55) and for a gift card below the
difference (L63). Authentication and the completeness of the list are not checked.

## Irreversible

`exchange_delivered_order_items` is declared irreversible. Policy sentences: L81 "After user confirmation, the order
status will be changed to 'exchange requested', and the user will receive an email regarding how to return items.
There is no need to place a new order."; tool description (L83): "For a delivered order, return or exchange can be
only done once by the agent." No tool reverses an exchange request. No delete-list.

## Policy silent / not modelled

As `retail_modify_pending_items`: the later collection of missing items, item ids and prices.

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
