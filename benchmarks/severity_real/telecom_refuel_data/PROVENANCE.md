# Provenance: telecom_refuel_data

Ported from tau2-bench `c06b07dd7c4d4ec61ba6ff9bcdf0b15dd7ef36d4` (2026-11-10): `_sources/tau2-bench/telecom/main_policy.md` (section "Data Refueling"),
`_sources/tau2-bench/telecom/tech_support_workflow.md` (step 2.1.4) and `_sources/tau2-bench/telecom/tools.py`
(`refuel_data`). Read as text only.

## What comes from where

| Element | Source |
|---|---|
| message `NoDataReport` | `tech_support_workflow.md` Path 2: unavailable mobile data |
| external (System): `limit_exceeded` (`usage_exceeded`) / `within_limit` (`usage_within`) | `tech_support_workflow.md` L176-181 "Step 2.1.4: Check Data Usage ... If Data Usage is EXCEEDED: Ask the user whether they want to change another plan or refuel data."; L188 "If Data Usage is NOT EXCEEDED: Ask user to run a speed test ..."; `main_policy.md` L132 "If the user's data usage for a line exceeds the plan's data limit, data connectivity will be lost. You can add more data to the line by 'refueling' data" |
| agent choice 1: `proceed_usage` (guard `usage_exceeded`, then message `AskRefuelAmount`) / `deny_usage` (guard `usage_within`) | same |
| external (User): `within_two_gb` (`amount_ok`) / `more_than_two_gb` (`amount_bad`) | `main_policy.md` L134 "The maximum amount of data that can be refueled is 2GB."; L136 "Ask them how much data they want to refuel" |
| agent choice 2: `proceed_amount` (guard `amount_ok`) / `deny_amount` (guard `amount_bad`) | L134; L11 "You should deny user requests that are against this policy." |
| message `ListDetailsAndAskConfirmation` (the price), external (User) `yes` / `not_yes` | L137 "Confirm the price." |
| agent choice 3: `execute` / `hold` | L137-138 "Confirm the price. Apply the refueled data to the line"; guard of `execute`: usage exceeded, amount within 2 GB, user confirmed the price |
| capability `refuel_data` | `tools.py` `refuel_data` |

Goal: usage exceeded and amount ok and (refueled and confirmed, or not confirmed and not refueled), or usage
within the limit or amount too large and not refueled.

## Tool-side checks

None modelled. `refuel_data` (`tools.py` L667-728) checks that the amount is positive and that the plan exists; the
check that the line is active is commented out (L689-690), and neither the 2 GB cap nor the usage condition is
checked. So both conditions are guards only, no `pre`.

## Irreversible

`refuel_data` is declared irreversible. Policy: L137-138 "Confirm the price. Apply the refueled data to the line
associated with the phone number the user provided." The tool charges the customer: "Refuels data for a specific
line, adding to the customer's bill" and calls `_apply_one_time_charge`; no tool in `tools.py` credits or removes a
charge. The judgement that a billed charge is final for the agent is mine.

## Policy silent / not modelled

* Choosing between refuelling and changing plan (the other option of step 2.1.4) is the user's choice and
  not modelled; the pack is the refuel branch only.
* The telecom policy has an explicit confirmation only for the price ("Confirm the price", L137), which is the
  user's yes modelled here.
* The price (rate times GB) is not modelled.

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
