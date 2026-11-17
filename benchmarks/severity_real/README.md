# Real protocols for the severity analysis

Two groups of protocols, none written for this paper, answer the objection that the
17-protocol severity benchmark (`src/skillc/data/severity_corpus.json`) is self-authored.

* Group 1, six multi-role protocols ported from the ProtoGuard repository
  (`experiments/cases/skills_safety/`, checkout at commit
  `ac501e883ee7df1bc587ff0e7db83270b6b65653`), each built from public multi-role agent skills.
* Group 2, twelve protocols ported from the customer-service policies of tau-bench and
  tau2-bench (Sierra Research; sources vendored in `_sources/`, commits in `_sources/SOURCES.txt`):
  the procedures in which the agent decides before an action the policy treats as final or
  consequential. Described from "Second group" below.

Layout, per case: `pack.json` (the pack), `PROVENANCE.md` (upstream files, what comes
from where, every modelling decision), `EXPECTED.md` (per-branch severity, k*, point of no
return, committed before the tool ran), `result.json` (`skillc severity pack.json --json`).
`FINDINGS.md` records expected-versus-observed; `compare_expected.py` does the comparison.

Method. (1) PROVENANCE.md and the pack: the Scribble protocol is translated as it stands
(same roles, choices, branch order, every message a `msg` node; branch labels name the
anonymous Scribble branches); the world (atoms, effects, goal) is added from the role files'
stated behaviour; no choice was added or removed. (2) EXPECTED.md for all cases, committed
together with the packs in `6f7658ba` before the tool was run on any of them. (3) The tool was
run, results compared. Skill and protocol files were read as text only; no model, no
network.

## Results (kmax = 4)

Counts: "tool" is all branch verdicts as the tool reports them (one per choice-node path and
world, so loops multiply them); "mis." is the same restricted to misselections (branches the
guard marks wrong).

| case | upstream repositories | roles | choice nodes | irreversible (declared) | k* | PNR action | tool B/F/C | mis. B/F/C | expected = observed |
|---|---|---|---|---|---|---|---|---|---|
| pr_review_merge | github/awesome-copilot | 4 | 2 | merge | 0 | merge | 316 / 0 / 16 | 150 / 0 / 16 | yes (332/332 verdicts) |
| doc_coauthor_ship | anthropics/skills | 4 | 1 | ship | 0 | ship | 11 / 0 / 1 | 5 / 0 / 1 | yes (12/12) |
| sdlc_release_gate | github/awesome-copilot | 7 | 1 | deploy | 0 | deploy | 11 / 0 / 1 | 5 / 0 / 1 | yes (12/12) |
| sdlc_release_gate_concurrent | github/awesome-copilot (same files) | 7 | 1 | deploy | 0 | deploy | 11 / 0 / 1 | 5 / 0 / 1 | yes (12/12) |
| sdlc_release_gate_concurrent_withhold | github/awesome-copilot (same files) | 7 | 1 (3 branches) | deploy | 0 | deploy | 11 / 6 / 1 | 5 / 6 / 1 | yes (18/18) |
| gem_dev_team | github/awesome-copilot | 7 | 2 | deploy | 0 | deploy | 17 / 2 / 5 | 5 / 2 / 5 | yes (24/24) |

Distinct (branch, world) classes, i.e. the rows of each EXPECTED.md table, B/F/C:
pr_review_merge 6/0/4, doc_coauthor_ship 2/0/1, sdlc_release_gate 2/0/1, concurrent 2/0/1,
concurrent_withhold 2/1/1, gem_dev_team 4/1/2. Totals over the six packs: 18 Benign-class,
2 Futile-class, 10 Catastrophic-class rows. All six k* are 0 and the PNR actions are
`merge`, `ship` and `deploy` (four packs); every one is an externally visible effect. Analysis time per pack 0.1 s to 17 s (pr_review_merge: 19,772 configurations).
Bystander check: 0 pairs, exact, for every pack (by construction; see FINDINGS.md).

Independence caveat. Three of the six rows are protocols over the same seven upstream
files (the sdlc family). Counting upstream skill sets, the benchmark has four: the four
pr-review files, three anthropics/skills files, seven sdlc files, seven gem-* files.

## Cases skipped

Rule: at least one choice point in the Scribble protocol and at least one action whose
real-world effect cannot be undone.

| case | upstream | reason |
|---|---|---|
| code_execution | microsoft/autogen | no choice point (three straight-line messages) |
| airline_seat | openai/openai-agents-python | no choice point |
| booking_saga | langchain-ai/langgraph | no choice point; its SOURCES.md also says no upstream file is identified for the three roles |
| agenticpay_settlement | none recorded | no choice point (eight straight-line messages) |
| content_pipeline | crewAIInc/crewAI-examples | no choice point |
| doc_pipeline, pr_merge | anthropics/skills, awesome-copilot | no choice point; superseded by doc_coauthor_ship and pr_review_merge |
| sdlc_release_gate_permit | awesome-copilot | no choice point |
| saga_commit | langchain-ai/langgraph (tutorial only) | has a commit/compensate choice, but its SOURCES.md says the transaction, votes and commit rule are "written for this case", patterned on two-phase commit; the upstream has none of it |
| react18_migration | awesome-copilot react18-* (commit 6a8fa297) | has a five-way choice, but the skill text states no irreversible action: all edits are to a working tree and the one deletion (`rm -rf node_modules package-lock.json`) is regenerated by the next `npm install`; declaring something irreversible would be my assumption |
| sdlc_release_gate_concurrent_withhold_v3 | awesome-copilot | same choice structure as concurrent_withhold plus two extra messages; its extra rule (one NO versus two or more NO) lives in `v1.refn` payload checks; omitted so that a near-duplicate is not counted again |

## What the analysis shows that the source files do not

* pr_review_merge. The Merger file states no condition on merging ("bias to delivery"), and
  the protocol orders the merge after both approvals, but approvals carry no world content.
  The tool shows that a single wrong SecurityApproved after one correct round merges
  a vulnerable change (k* = 0), and that the loop makes wrong-round choices Catastrophic as
  long as such an approval stays within budget. None of the four files says so.
* doc_coauthor_ship. The only real gate is the DocLead's reader-test judgement; styling
  cannot reject, and `ship` is the sole irreversible step. One premature `style` ships an
  announcement with its gaps unfixed. The protocol is correct on every intended path and
  tolerant of nothing beyond that.
* sdlc_release_gate (three variants). Relay chain, fan-in and a three-way choice with a
  withhold ending give the same k* = 0 and the same point of no return; only the guard on
  `deploy` matters. The withhold branch is the one wrong choice that is Futile, not
  Catastrophic: refusing to ship costs the goal but burns nothing, which is what the case
  added the branch for.
* gem_dev_team. gem-devops' own pre-deploy check turns the premature-deploy branch from
  Catastrophic into Futile, but skipping the critic on a high-risk change is Catastrophic
  because the check does not cover it. The production approval gate in the skill has no
  counterpart in the protocol (FINDINGS.md).

## Second group: tau-bench and tau2-bench customer-service policies

Twelve protocols, one per policy procedure in which the agent decides before an action that
moves money or changes a booking. Per case the same files as group 1 (`pack.json`,
`PROVENANCE.md`, `EXPECTED.md`, `result.json`) plus `result_allworlds.json` (see below).
Pre-registration commit `2adce999` (packs, PROVENANCE.md, EXPECTED.md for all twelve and the
`_sources` folder, before the tool was run on any of them; only schema validation was used);
results and the comparison are in the following commits, `FINDINGS.md` classifies them.

Method. The sources are policies, not Scribble protocols, so the protocol is read off the
policy text (conventions shared by all twelve are in each PROVENANCE.md):

* roles `User`, `Agent`, `System`; only the Agent makes the analysed (agent) choices;
* every rule "only if C" is an agent choice, carry on or refuse, with explicit guards taken
  from the policy sentence; no choice uses the default guard;
* what the user asks or answers and what the records show are EXTERNAL choices whose branches
  are the cases the policy distinguishes (the tool resolves them adversarially, so the goal must
  be reachable in every world); the explicit-yes rule is an external choice of the user
  (`yes` / `not_yes`) followed by the agent's `execute` / `hold`;
* `pre` on the irreversible capability is exactly what the tool code checks itself (the
  retail tools and four airline tools were vendored); a condition the policy states but the
  tool does not check ("The API does not check these for the agent") is a guard only;
* the irreversible action is declared with the policy sentence quoted in PROVENANCE.md.

Where the policy is silent: the airline policy's explicit-yes list names booking, flight
changes, baggage, cabin and passenger updates, not cancellation or compensation, so those two
protocols have no confirmation node; the telecom policy asks only to confirm a price. Nothing
was added where the policy is silent.

### Results (kmax = 4)

"choice nodes" counts the static agent choices; "ext." the static external choices. "all worlds"
is the verdict count with every environment branch recorded (`analyze_all_worlds.py`),
"mis." the same restricted to misselections (branches the guard marks wrong), "stock" the
count in the stock tool's `result.json` (it stops recording at the first hazardous environment
branch, see FINDINGS.md).

| case | source | choice nodes | ext. | irreversible (declared) | k* | all worlds B / F / C | mis. B / F / C | stock B / F / C |
|---|---|---|---|---|---|---|---|---|
| airline_cancel_reservation | tau-bench airline | 2 | 2 | cancel_reservation | 0 | 7 / 10 / 7 | 0 / 10 / 7 | 1 / 1 / 2 |
| airline_modify_flights | tau-bench airline | 3 | 4 | update_reservation_flights | 0 | 35 / 11 / 10 | 7 / 11 / 10 | 4 / 0 / 2 |
| airline_baggage_update | tau-bench airline | 2 | 2 | update_reservation_baggages | 0 | 6 / 2 / 4 | 0 / 2 / 4 | 3 / 2 / 1 |
| airline_change_cabin | tau2-bench airline | 3 | 3 | change_cabin | 0 | 15 / 3 / 10 | 1 / 3 / 10 | 4 / 0 / 2 |
| airline_book_reservation | tau-bench airline | 3 | 3 | book_reservation | 0 | 23 / 7 / 10 | 3 / 7 / 10 | 4 / 3 / 1 |
| airline_compensation | tau2-bench airline | 3 | 3 | send_certificate | 0 | 19 / 4 / 25 | 1 / 4 / 25 | 3 / 3 / 1 |
| retail_cancel_pending_order | tau-bench retail | 4 | 4 | cancel_pending_order | 0 | 55 / 22 / 7 | 13 / 22 / 7 | 5 / 4 / 1 |
| retail_modify_pending_items | tau-bench retail | 5 | 5 | modify_pending_order_items | 0 | 103 / 47 / 6 | 25 / 47 / 6 | 6 / 5 / 1 |
| retail_return_delivered_order | tau-bench retail | 4 | 4 | return_delivered_order_items | 0 | 40 / 16 / 4 | 10 / 16 / 4 | 5 / 4 / 1 |
| retail_exchange_delivered_order | tau-bench retail | 5 | 5 | exchange_delivered_order_items | 0 | 103 / 47 / 6 | 25 / 47 / 6 | 6 / 5 / 1 |
| telecom_refuel_data | tau2-bench telecom | 3 | 3 | refuel_data | 0 | 15 / 3 / 10 | 1 / 3 / 10 | 4 / 3 / 1 |
| telecom_overdue_payment_resume | tau2-bench telecom | 2 | 3 | make_payment | 0 | 6 / 4 / 2 | 0 / 4 / 2 | 5 / 4 / 1 |

Expected = observed for all 704 all-worlds verdicts (distinct (branch, world) classes: the 12 EXPECTED
tables have 8, 14, 8, 13, 15, 15, 19, 24, 19, 24, 13 and 8 rows, i.e. 180 rows, every one observed).
The stock `result.json` files agree on every verdict they contain (99) and on k* and the
point-of-no-return action, but leave 83 rows unobserved. Analysis time per pack 0.05 s to 0.7 s.
Bystander check: 0 pairs, exact, for every pack (by construction, as in group 1).

Independence caveat. `retail_modify_pending_items` and `retail_exchange_delivered_order`
have the same choice structure and counts (the two procedures share their rules); the airline
packs come from two vintages of the same domain policy (tau-bench `wiki.md` for cancel, modify,
baggage and booking; the tau2-bench `policy.md` for cabin and compensation, whose rules for the
shared procedures are near-identical). The group is twelve protocols, not twelve independent
structures.

### What the analysis shows that the policy texts do not

* Where the tool enforces a rule, a wrong choice is harmless; where only the policy states it,
  it is a point of no return. All four retail tools check the order status, the reason, the
  item and the payment method themselves, so every misselected rule gate there is Benign or
  Futile; the one rule no retail tool checks is authentication, and that gate is Catastrophic
  (`proceed_auth`). In the airline and telecom packs the policy says outright, or the tool
  code shows, that the rule is not checked ("The API does not check these for the agent":
  cancellation grounds, basic economy and route changes; remove-bags; more than five
  passengers or too many payment methods of one kind; the 2 GB cap and the usage condition of
  data refuelling; "overdue" before a payment request), and each such gate is Catastrophic.
* Every protocol has k* = 0. For the nine with an explicit yes the reason is not the rule gates
  but the confirmation itself: a user answer other than yes followed by an `execute` is one
  misselection from a point of no return, whatever the earlier gates did. For the three
  without one (cancellation, compensation, overdue payment) the decision itself is the single
  gate before the irreversible action. The explicit-yes rule does not raise k* in this model;
  it adds a hazard that exists only if the agent ignores the answer (FINDINGS.md, sensitivity).
* The items-complete reminder of the two retail item procedures matters only because the tool
  can be called once: `execute` with items still to add is Catastrophic for no other reason.

### Distribution over the whole real group (18 protocols)

* k*: 18 protocols at k* = 0, none above. Nothing in the group has k* > 0, so there is no
  tolerant protocol to explain. The point-of-no-return actions are `merge`, `ship`, `deploy`
  (group 1) and the twelve declared tau actions (cancel, modify, return, exchange, book,
  update baggage or flights, change cabin, send certificate, refuel data, make payment).
* Agent choice nodes (static): 1 node in 4 protocols, 2 in 5, 3 in 5, 4 in 2, 5 in 2 (47
  nodes in total; group 1: 8 nodes in 6 protocols, group 2: 39 nodes in 12 protocols, mean
  3.25). Static external choices: 0 in group 1, 41 in group 2 (mean 3.4).
* Independent sources. Group 1: four upstream skill sets from two repositories (the four
  pr-review files, three anthropics/skills files, seven sdlc files, seven gem-* files; the last
  three from github/awesome-copilot). Group 2: four policy documents from two repositories
  (tau-bench airline, tau-bench retail, tau2-bench airline, tau2-bench telecom). The real
  group therefore has eight upstream document sets from four repositories; counting the two
  airline policies once (same domain), seven distinct sources. Eighteen protocols over them.

Protocols with k* > 0: none. The k* = 0 outcome is again a property of the structure (one
irreversible action behind agent-judged gates and a user answer the agent may ignore), so
the row is not an estimate of how common k* = 0 is among real protocols; k* >= 5 occurs in the
authored benchmark only.

### Cases skipped (second group)

Rule as for group 1, with the irreversible action stated by the policy or its tool.

| procedure | source | reason |
|---|---|---|
| modify pending order address, modify user default address | tau-bench retail | the policy states no finality: an address can be changed again |
| modify pending order payment | tau-bench retail | money moves (L53: the original payment method is refunded), but the action is repeatable: the tool only requires the new method to differ from the current one (`modify_pending_order_payment.py` L38), so the policy does not make it final; declaring it irreversible would be my assumption |
| change passengers | tau-bench / tau2-bench airline | the count rule is checked by the tool (`update_reservation_passengers.py` L20) and the policy does not mark the change final; not conflated with the baggage action |
| add insurance after booking | airline | no tool exists (the airline tool set has no insurance update) |
| resume a suspended line without the payment step | tau2-bench telecom | `resume_line` is reversible (`suspend_line` exists); it appears as the second choice of `telecom_overdue_payment_resume` |
| change plan | tau2-bench telecom | the policy has the steps but `tools.py` has no plan-change tool and no finality is stated |
| enable / disable roaming | tau2-bench telecom | reversible (`disable_roaming`) and free |
| transfer to a human agent | all | a hand-off; the policy states no finality |
| technical-support troubleshooting paths | tau2-bench telecom | user-side device actions, no agent decision before a consequential action |

## Reproduce

    PYTHONPATH=src python3 -m skillc.cli severity benchmarks/severity_real/<case>/pack.json --json
    PYTHONPATH=src python3 benchmarks/severity_real/analyze_all_worlds.py     # group 2: result_allworlds.json
    python3 benchmarks/severity_real/compare_expected.py
    python3 scripts/severity_eval.py        # regenerates paper/WIP/results/severity.json, docs/SEVERITY_RESULTS.md
    PYTHONPATH=src python3 -m pytest -q -p no:cacheprovider tests/test_severity.py

k* values may move if the default guard in `severity.py` changes; the explicit guards used
here do not depend on that default, but `deploy`/`merge`/`ship` hazards use the
derived goal-reachability check, and tests/test_severity.py will flag any drift.
