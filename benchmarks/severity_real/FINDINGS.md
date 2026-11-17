# Findings: expected versus observed

Group 1 (six ProtoGuard cases): pre-registration commit `6f7658ba` (packs, PROVENANCE.md,
EXPECTED.md for all six cases, before the tool was run on any of them). Group 2 (twelve
tau-bench / tau2-bench cases): pre-registration commit `2adce999`; its findings are in the
last part of this file ("Group 2"). Results: `<case>/result.json`; comparison:
`python3 compare_expected.py`.

# Group 1 (ProtoGuard cases)

## Disagreements

None. For all six packs the tool's k*, point-of-no-return action and every one of the
branch verdicts (12, 24, 332, 12, 12, 18 verdicts) match EXPECTED.md, and every row of every
EXPECTED table was observed. There is therefore nothing to classify as (a) modelling
error, (b) wrong expectation or (c) surprise, and no fix commit exists.

How much that agreement is worth. It is an implementation check against hand
reasoning, not a test of the world models. The guards are explicit, so each verdict is
close to determined by the pack: given the guard and the irreversible tool, whether a
branch is Catastrophic follows from a short reachability argument. The expectations were
derived after reading `severity.py` and the paper's definition of severity. What the
benchmark does test is whether real skill and protocol files can be translated into packs
at all, and which hazards survive that translation.

## Findings of type (c): hazards the source skill files do not guard against

Each is a hazard the tool reports at k* = 0 (one misselection) that no role file excludes.
The hazard in every case is "an irreversible action fires while an earlier gate was passed
wrongly", and the guard condition that makes the gate's wrong branch wrong is stated by
the case or by one role's file, never enforced at the irreversible action.

1. `pr_review_merge`, `merge`. The Merger file says "merge as soon as you judge the change
   ready ... bias to delivery" and states no condition. One wrong `SecurityApproved`
   (after one correct review round) reaches `merge` with the vulnerability open. The
   Scribble protocol orders the merge after both approval messages; the approval messages
   carry no world content, so ordering alone does not prevent it.
2. `doc_coauthor_ship`, `ship`. A wrong `style` branch ships a document whose reader-test
   gaps were never fixed. BrandStyler cannot catch it: the upstream skill has no
   approve/reject language (the case README documents this).
3. `sdlc_release_gate`, `_concurrent`, `_concurrent_withhold`, `deploy`. The condition
   "ships only after all four reviews pass" is the case's role description, not text of the
   upstream Merger skill; the DevOps skill states no review precondition (its example
   pipeline gates deploy on `build` and `npm test`). One wrong `approve` deploys with a
   review still rejecting. The same k* = 0 and the same point of no return appear for the
   relay-chain, fan-in and three-way-choice protocols: communication structure does not
   change severity here; the guard on `deploy` does.
4. `gem_dev_team`, `deploy`. The only pack with a pre-deploy condition stated by a role
   file (gem-devops "Pre-Deploy: tests passing, code review ..."). It shields choice 2: a
   premature `tests_passed` is Futile (blocked), not Catastrophic. It does not shield
   choice 1: `skip_critic` on a high-risk change loses the goal (the critic never runs) and
   the loop later reaches `deploy` on the intended path, a point of no return with zero
   further misselections.

## Where the source files and the protocols disagree with each other

* gem-devops states: "IF requires_approval OR devops_security_sensitive OR environment =
  production: return `needs_approval`" and deploys only after the orchestrator re-delegates
  with approval. The Scribble protocol has no approval message, so the production approval
  gate has no place in the pack. A pack faithful to the skill would block `deploy`
  until an approval step runs; the protocol cannot express that. Not a tool finding: a
  protocol-versus-skill gap found while porting.
* The DevOps skills (sdlc, gem) state rollback commands. They are not in any protocol step
  and `deploy` is declared irreversible regardless (judgement, see each PROVENANCE.md).

## Sensitivities and limits recorded here

* Declared irreversibility is the load-bearing modelling decision. All four hazards above
  rest on `merge`, `ship` or `deploy` being declared irreversible; with no delete-lists
  modelled, removing the declarations makes every pack tolerant at every k (nothing is a
  point of no return). Not run; follows from `permanent_deletes` being empty.
* gem_dev_team: if the pre-deploy item "code review" were read to include the critic's
  review, `skip_critic` would be blocked at `deploy` and Futile, and the pack would be
  tolerant at every k. The pack reads it as the plan review only (`plan_approved`). Not run.
* Worlds are the hazard worlds (findings open, gaps open, tests red, high risk). A clean
  world makes every guard-intended branch Benign and every wrong branch a detour; those
  worlds are not ported.
* All six packs come out k* = 0. That is a property of how the worlds were chosen (hazard
  worlds, one gate before an irreversible tool), so the six rows are not an estimate of how
  common k* = 0 is among real protocols. The k* >= 5 outcome is exercised by the authored
  benchmark, not by this one.
* Raw verdict counts overstate the number of distinct situations. The tool keys a verdict by
  choice-node path, and a `rec` unfolds the path at every visit: `pr_review_merge` reports
  332 branch verdicts (16 Catastrophic) for what EXPECTED.md describes with 10 rows (4
  Catastrophic). The README gives both.
* The bystander check (Interleave.v) reports 0 pairs, exact, for every pack. This is by
  construction: every act was placed directly after the message addressed to its owner,
  which is where the Scribble causality puts it, so no act can be moved across another
  node. It says nothing about ungated deployments of real skills.
* The explicit guards on gate choices (finding open => revise) are the case's or the skill's
  statement of "wrong"; the analysis cannot tell whether a real agent holds that belief.


# Group 2: tau-bench and tau2-bench customer-service policies

Pre-registration commit: `2adce999` (twelve packs, PROVENANCE.md and EXPECTED.md for all of
them, and `_sources/`, before the tool was run on any of them; only `Pack.load` /
`validate_pack` was used). Results commit: the next one. No pack, PROVENANCE.md or EXPECTED.md
was edited after the tool ran.

## Disagreements and their classification

`python3 compare_expected.py` on the stock tool's `result.json` reports DISAGREE for 11 of the 12
packs (all but `telecom_overdue_payment_resume`). Every disagreement has the same form and
none concerns a severity:

* 0 mismatches (an observed verdict with a severity other than the expected one), 0 unmatched
  verdicts, k* and the point-of-no-return action equal EXPECTED.md for all 12; the 99 verdicts the
  stock tool recorded all match their rows;
* 83 rows of the EXPECTED tables are unobserved (baggage 2, booking 7, cancel 4, cabin 7,
  compensation 8, modify flights 8, retail cancel 9, retail exchange 12, retail modify items 12,
  retail return 9, refuel 5).

Cause. `SeverityAnalyzer.hazard_within` records a verdict for every branch of an agent choice
even after a hazard was found (its comment says so, and it is what makes the group-1 counts
complete). Its loop over the branches of an EXTERNAL choice, by contrast, returns at the first
branch in which a hazard is found, also while recording:

    for label, br in body["branches"].items():
        ...
        found, wit, pnr = self.hazard_within(list(br) + rest, bst, ...)
        if found:
            return True, wit, pnr          # <-- stops recording the remaining environment branches

With the full budget of 4 almost every environment branch contains a hazard, so only the first
environment branch (and the first branch of the next external choice, and so on) is recorded.
k* and the point of no return come from the budget scan, which needs only the first hazard, and
are unaffected. Group 1 has no external choice, so none of its results changes.

Classification: type (c), a finding about the tool, not (a) a modelling error (no pack was
wrong: each unobserved row is observed once the recording is complete) and not (b) a wrong
expectation of a severity (no severity was wrong). One part of the expectation WAS wrong: the
tables were written on the assumption that all environment branches are recorded; that was an
assumption about the tool, and it does not hold. Handling, without editing `src/skillc/severity.py`
(off limits on this branch, and not a crash): `analyze_all_worlds.py` takes the tool's own
`hazard_within` source at import time and substitutes exactly one loop, so that while recording every
environment branch is visited and the first hazard seen is kept (it fails loudly if the tool's text
changes; `tests/test_severity.py` checks that it equals the tool on the six packs without external
choices). `result_allworlds.json` is its output. Against it: 704 verdicts, 0 mismatches, 0 unmatched,
all 180 rows observed, k* and PNR equal. The proposed fix to the tool is the same change, six lines:

    -                        if found:
    -                            return True, wit, pnr
    -                    return False, (), None
    +                        if found:
    +                            if not record:
    +                                return True, wit, pnr
    +                            first_env = first_env or (True, wit, pnr)
    +                    return first_env or (False, (), None)

(with `first_env = None` before the loop). Until the tool is changed, `scripts/severity_eval.py`
uses the complete recorder for the group-2 packs, so `docs/SEVERITY_RESULTS.md` and
`results/severity.json` count all worlds; the stock counts stay in `result.json`.

There is no type (a) disagreement, so there is no fix commit, and no type (b) severity disagreement.
How much that agreement is worth is as for group 1: an implementation check against hand
reasoning; the guards, the tool-side `pre` and the declarations are explicit, so each verdict
follows from a short reachability argument. What the group tests is whether policy text, read with
its tool code, can be turned into packs, and which hazards survive.

## Findings of type (c): hazards the policy texts leave to the agent

1. Enforced versus unenforced rules. For every rule the pack records whether the tool code checks
   it. A rule the tool enforces is not a hazard: the retail status, reason, item, payment and
   refund-destination gates are Benign or Futile when misselected, because the tool refuses
   the call. A rule the tool does not enforce is a point of no return one wrong
   `execute` later: authentication (all four retail packs; no retail tool checks it);
   cancellation grounds and the flown rule (`cancel_reservation` "does not check", wiki L58);
   basic economy and route changes (L44); "add but not remove" bags (the tool overwrites the
   count); more than five passengers and more than one certificate / credit card / three gift
   cards (the tool checks only that a method exists and covers its share); the 2 GB cap and the
   "usage exceeded" condition of data refuelling (`refuel_data` checks only a positive amount);
   "bill is overdue" before a payment request (the docstring warns it does not check). The
   airline policy says so itself ("The API does not check these for the agent, so the agent must
   make sure the rules apply before calling the API!"); the retail tool code encodes its policy
   almost completely, the airline and telecom tool code does not.
2. k* = 0 everywhere, for two different reasons. In the nine packs with an explicit yes
   (modify flights, baggage, cabin, booking, retail cancel / modify items / return / exchange, refuel)
   the one-misselection hazard is `execute` after a not-yes answer (or, for the item procedures,
   with items still to add), reachable from any world in which the rules hold. A wrong rule gate
   alone is not a one-misselection hazard there: it needs a second wrong choice (the `execute`),
   the verdict is Catastrophic only because the budget (4) covers it. In the three packs without
   an explicit yes (cancellation, compensation, overdue payment) the decision itself is the
   single gate.
3. Cancellation and compensation have no confirmation in the airline policy. The yes list (L7)
   names booking, flight changes, baggage, cabin and passenger updates. `airline_cancel_reservation`
   and `airline_compensation` therefore have the decision as their only gate (k* = 0; 7 and 25
   Catastrophic verdicts over all worlds). The
   policy gives the agent no user-side check on either; the tool checks neither.
4. Compensation: three independent gates (user asked, profile, reason) and a wrong amount are each
   a point of no return, because `send_certificate` accepts any amount for any user.
5. Telecom overdue payment: the user's acceptance of the payment request is the only user step
   and does not protect (the model lets the user accept; the pay action is final): one
   `send_request` for a bill that is not overdue is a point of no return.
6. Retail item procedures: the reminder "confirm they have provided all items" matters only
   because the call is once-only: `execute` with items still to add is Catastrophic.

## Where the policy texts, the tool code and the protocol disagree with each other

* Telecom: the policy gives a 2 GB maximum for refuelling; `refuel_data` does not check it
  (`gb_amount <= 0` is the only amount check), and a commented-out line shows the active-line
  check was removed.
* Airline: the policy says bags cannot be removed; `update_reservation_baggages` overwrites the
  counts. The policy says passengers cannot be changed in number; the tool does check it.
* The tau-bench airline wiki (`L7`) and the tau2 policy list the same actions for explicit
  confirmation; neither includes cancel or compensation, while the retail wiki's list (cancel,
  modify, return, exchange) covers them all.
* tau-bench airline lists gold business baggage as 3; tau2 lists 4 (L94). Not modelled (no guard).

## Sensitivities and limits recorded here

* Declared irreversibility is load-bearing, as in group 1: with no declaration nothing is a point
  of no return. Not run. Several declarations are my judgement, marked in each PROVENANCE.md
  (cabin change, flight update, refuel charge); the others quote the policy or the tool.
* The `not_yes` branch is demonic and the user cannot catch an agent error: the model has no way
  to say that a user who is shown wrong details declines. By hand (not run): without the `not_yes`
  and `more_items_to_add` branches every one of the nine explicit-yes packs would need two
  misselections for a hazard (a wrong rule gate, then `execute`), so k* = 1 for them; their k* = 0
  rests on that branch. The explicit-yes rule therefore protects nothing in this model against
  an agent that ignores the answer; it only forces the hazard to be an `execute` rather than a
  gate.
* `pre` = what the tool checks. If the tool checks were treated as guards only, the retail gates
  would become Catastrophic (by the verdict rule; not run); the tau2 airline tool code was not
  vendored, so cabin change and compensation have no `pre` at all.
* The worlds are every combination of the external choices, not a single hazard world; verdict
  counts therefore multiply (156 verdicts for 24 EXPECTED rows) and are not a count of distinct
  situations. The EXPECTED tables are the distinct classes.
* Siblings: `retail_modify_pending_items` and `retail_exchange_delivered_order` have the same
  structure and the same counts; the airline protocols come from two vintages of one domain.
* Not modelled (see each PROVENANCE.md): values no guard reads, airline identity (the policy asks
  for the user id only), the single-tool-call and no-opinion rules, the continuation after the
  irreversible call (collecting missing items, the reboot after resuming a line), the user's later
  provision of a valid payment method after `ask_other_*`.
* Bystander: 0 pairs for every pack, by construction (every act is first in its branch or follows
  a message to its owner).
