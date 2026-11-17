# Provenance: telecom_overdue_payment_resume

Ported from tau2-bench `c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4` (2026-11-10): `_sources/tau2-bench/telecom/main_policy.md` (sections "Overdue Bill Payment" and "Line
Suspension") and `_sources/tau2-bench/telecom/tools.py` (`send_payment_request`, `resume_line`). Read as text
only.

## What comes from where

| Element | Source (`main_policy.md`) |
|---|---|
| message `NoServiceReport` | "Line Suspension": a suspended line means no service |
| external (System): `overdue` (`bill_overdue`) / `not_overdue` (`bill_not_overdue`) | L105 "Check the bill status to make sure it is overdue."; L117 "The send payement request tool will not check if the bill is overdue. You should always check that the bill is overdue before sending a payment request." |
| external (System): `contract_valid` (`contract_ok`) / `contract_ended` (`contract_ended`) | L126 "You are not allowed to lift the suspension if the line's contract end date is in the past, even if the user has paid all their overdue bills." |
| agent choice 1: `send_request` (guard `bill_overdue`) / `no_request` (guard `bill_not_overdue`) | L105-108 "Check the bill status ... Send the user a payment request for the overdue bill."; L117 |
| external (User): `accepts` / `declines` | L110-111 "Inform the user that a payment request has been sent. ... If the user accepts the payment request, use the make_payment tool to make the payment." |
| capability `make_payment` (owner User, adds `bill_paid`); `decline_request` (adds `request_declined`) | L111; L112 "After the payment is made, the bill status will be updated to PAID."; message `BillStatusPaid` (L113 "Always check that the bill status is updated to PAID before informing the user") |
| agent choice 2: `resume` (guard `contract_ok`) / `refuse_resume` (guard `contract_ended`) | L125 "You are allowed to lift the suspension after the user has paid all their overdue bills."; L126 |
| capabilities `send_payment_request`, `resume_line` | `tools.py` |

Goal: overdue, contract ok, paid and resumed; or overdue, contract ended, paid and not resumed; or overdue and
the user declined the request and not paid; or the bill is not overdue and not paid.

## Tool-side checks

None modelled. `send_payment_request` (`tools.py` L420-453) refuses when another bill is already awaiting payment
or the bill is not the customer's, and its docstring warns "This method does not check if the bill is already
PAID. Always check the bill status before calling this method." So "is overdue" is a guard only. (The
one-bill-awaiting rule, L116, is checked by the tool and is not modelled: it only blocks the request.)

## Irreversible

`make_payment` is declared irreversible; its owner is the User (the customer's own payment; the policy says "use
the make_payment tool" after the user accepts). Policy: L111-112 (the payment is made and the bill becomes PAID).
It moves money and no tool in `tools.py` refunds it. `send_payment_request` (the agent's action) is not declared
irreversible: it only sets the bill to AWAITING PAYMENT. `resume_line` is not declared irreversible either: the
policy states no finality and `suspend_line` exists in `tools.py` (the line can be suspended again).

## Policy silent / not modelled

* The telecom policy has no explicit-yes rule for the agent's own actions; the user's accept / decline of the
  payment request is its confirmation step, modelled as the external choice. There is no separate
  confirmation node.
* The `declines` branch ends the protocol (nothing is paid, the suspension stays).
* The suspension reason (overdue bill or contract end) is folded into the two system facts; a line suspended for
  both reasons is the `contract_ended` branch.
* `resume_line` is reached only after payment (L125). If the bill was not overdue and the user nonetheless paid
  (a misselected request), the resume guard still reads only the contract.

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
