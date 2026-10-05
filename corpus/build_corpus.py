"""
build_corpus.py  --  emits corpus.json

Each entry pairs a natural-language skill (what an author writes) with its
*reference compaction* (the formal pack an LLM distills from that NL), a
ground-truth semantic label, and the failure category it exercises.

Ground truth is the TRUE semantic achievability of the goal.  The eval then
measures the checker against it.  The key claims under test:

  * NO false "IMPOSSIBLE"  (soundness, Coq T1)  -> false-negatives must be 0
  * SOME false "ACHIEVABLE" allowed (paper Incompleteness proposition) -> the spurious
    cases, each annotated with which residue (payload / intent) caused it.

Categories trace the user's own failure docs:
  HALLUCINATED_PLANNING  (infinite-loop doc, failure mode 2)
  INFINITE_LOOP / NO_PROGRESS (failure mode 1)
  DEADLOCK / NON_PROJECTABLE  (STJP one-pager, the freeze)
  REFINEMENT  (budget constraints)
  ACHIEVABLE / TOLERANCE  (detours, extra messages, subtyping)
  SPURIOUS  (T3 incompleteness demonstrations)
"""
import json
import os
from collections import Counter

C = []

def add(id, category, ground_truth, nl, pack, note="", environment_grants=None,
        input_type="skill"):
    C.append({"id": id, "category": category, "ground_truth": ground_truth,
              "nl": nl.strip(), "pack": pack, "note": note,
              "environment_grants": (
                  list(pack["capabilities"])
                  if environment_grants is None else environment_grants),
              "input_type": input_type})

# ---------------------------------------------------------------- ACHIEVABLE
add("book_flight_ok", "ACHIEVABLE", "ACHIEVABLE",
"""
# Skill: Book a flight and confirm
Goal: the customer has a booked flight and a confirmation email is sent.
Tools: search_flights, filter_results, book_flight, send_email.
Steps: search, then filter, then book, then email the confirmation.
""",
{"name":"book_flight_ok","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "filter":{"owner":"agent","pre":"searched","add":["filtered"]},
   "book":{"owner":"agent","pre":"filtered","add":["booked"]},
   "email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"filter","by":"agent"}},
             {"act":{"cap":"book","by":"agent"}},
             {"act":{"cap":"email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent"]}})

add("budget_ok", "REFINEMENT", "ACHIEVABLE",
"""
# Skill: Book a flight under $500
Goal: a flight is booked at a price below 500 and confirmation is sent.
Tools: search, book_cheap (only books fares under 500), send_email.
""",
{"name":"budget_ok","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "book_cheap":{"owner":"agent","pre":"searched","add":["booked"],
                 "nondet":{"price":{"cmp":["price","<",500]}}},
   "email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"book_cheap","by":"agent"}},
             {"act":{"cap":"email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent",{"cmp":["price","<",500]}]}})

add("detour_ok", "TOLERANCE", "ACHIEVABLE",
"""
# Skill: Research then answer (with optional clarification)
Goal: a researched answer is delivered.
The worker may first ping the user with a status note (a detour that does not
change the outcome), then search, then deliver.
""",
{"name":"detour_ok","roles":["worker","user"],
 "capabilities":{
   "search":{"owner":"worker","add":["searched"]},
   "deliver":{"owner":"worker","pre":"searched","add":["answered"]}},
 "protocol":[{"msg":{"from":"worker","to":"user","label":"status_note"}},
             {"act":{"cap":"search","by":"worker"}},
             {"msg":{"from":"worker","to":"user","label":"status_note2"}},
             {"act":{"cap":"deliver","by":"worker"}}],
 "goal":"answered"},
 note="extra status messages (payload-level detail) must not refute the goal")

add("choice_informed_ok", "TOLERANCE", "ACHIEVABLE",
"""
# Skill: Triage then handle
Goal: the ticket is resolved.
The router picks 'simple' or 'complex' and TELLS the handler which path it
chose; the handler then resolves accordingly.
""",
{"name":"choice_informed_ok","roles":["router","handler"],
 "capabilities":{
   "resolve_simple":{"owner":"handler","add":["resolved"]},
   "resolve_complex":{"owner":"handler","add":["resolved"]}},
 "protocol":[{"choice":{"by":"router","branches":{
     "simple":[{"msg":{"from":"router","to":"handler","label":"go_simple"}},
               {"act":{"cap":"resolve_simple","by":"handler"}}],
     "complex":[{"msg":{"from":"router","to":"handler","label":"go_complex"}},
                {"act":{"cap":"resolve_complex","by":"handler"}}]}}}],
 "goal":"resolved"})

# --------------------------------------------------------- IMPOSSIBLE (sound)
add("hallucinated_email", "HALLUCINATED_PLANNING", "IMPOSSIBLE",
"""
# Skill: Book a flight and confirm
Goal: flight booked AND confirmation email sent.
Required tools: search, filter, book, send_email.
Plan: search, filter, book, then send the confirmation email.
""",
{"name":"hallucinated_email","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "filter":{"owner":"agent","pre":"searched","add":["filtered"]},
   "book":{"owner":"agent","pre":"filtered","add":["booked"]},
   "send_email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"filter","by":"agent"}},
             {"act":{"cap":"book","by":"agent"}},
             {"act":{"cap":"send_email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent"]}},
 note="environment omits the required send_email grant -> MISSING_CAPABILITY",
 environment_grants=["search", "filter", "book"])

add("no_establisher", "HALLUCINATED_PLANNING", "IMPOSSIBLE",
"""
# Skill: Book a flight and confirm
Goal: flight booked AND confirmation sent.
Required tools: search, filter, book, notify_customer.
Plan: search, filter, book, then notify the customer.
""",
{"name":"no_establisher","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "filter":{"owner":"agent","pre":"searched","add":["filtered"]},
   "book":{"owner":"agent","pre":"filtered","add":["booked"]},
   "notify_customer":{"owner":"agent","pre":"booked","add":["notification_queued"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"filter","by":"agent"}},
             {"act":{"cap":"book","by":"agent"}},
             {"act":{"cap":"notify_customer","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent"]}},
 note="the granted notifier only queues work; no capability establishes confirmation_sent")

add("over_budget", "REFINEMENT", "IMPOSSIBLE",
"""
# Skill: Book a flight under $500
Goal: flight booked under 500 and confirmation sent.
The only booking tool available books premium fares (>= 800).
""",
{"name":"over_budget","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   "book_premium":{"owner":"agent","pre":"searched","add":["booked"],
                   "nondet":{"price":{"cmp":["price",">=",800]}}},
   "email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"book_premium","by":"agent"}},
             {"act":{"cap":"email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent",{"cmp":["price","<",500]}]}},
 note="refinement on price is unsatisfiable along every run -> GOAL_UNSAT")

add("blocked_precondition", "INFINITE_LOOP", "IMPOSSIBLE",
"""
# Skill: Publish a report
Goal: the report is published.
Tools: draft, publish.
The publish tool requires the report to be DRAFTED and APPROVED.
Plan: draft, then publish.
""",
{"name":"blocked_precondition","roles":["agent"],
 "capabilities":{
   "draft":{"owner":"agent","add":["drafted"]},
   "publish":{"owner":"agent","pre":{"and":["drafted","approved"]},
              "add":["published"]}},
 "protocol":[{"act":{"cap":"draft","by":"agent"}},
             {"act":{"cap":"publish","by":"agent"}}],
 "goal":"published"},
 note="guard 'approved' never establishable -> BLOCKED_GUARD (the retry-forever cause)")

add("deadlock_unobserved", "DEADLOCK", "IMPOSSIBLE",
"""
# Skill: Plan / worker collaboration
Goal: the task result is delivered.
The worker decides whether to ASK a clarifying question or to DELIVER. In the
'ask' branch the planner answers before the worker delivers. The branch choice
is local to the worker; no branch-label message precedes the planner's action.
""",
{"name":"deadlock_unobserved","roles":["planner","worker"],
 "capabilities":{
   "answer":{"owner":"planner","add":["answered"]},
   "deliver":{"owner":"worker","pre":"answered","add":["delivered"]},
   "deliver_direct":{"owner":"worker","add":["delivered"]}},
 "protocol":[{"choice":{"by":"worker","branches":{
     "ask":[ {"act":{"cap":"answer","by":"planner"}},   # planner must act...
             {"act":{"cap":"deliver","by":"worker"}}],  # ...but was never told
     "direct":[{"act":{"cap":"deliver_direct","by":"worker"}}]}}}],
 "goal":"delivered"},
 note="planner must act in 'ask' branch with no distinguishing receive -> NON_PROJECTABLE")

add("missing_tool_chain", "HALLUCINATED_PLANNING", "IMPOSSIBLE",
"""
# Skill: Refund a customer
Goal: refund issued AND ledger updated.
Required tools: lookup, refund, update_ledger.
Plan: look up the order, issue the refund, then update the ledger.
""",
{"name":"missing_tool_chain","roles":["agent"],
 "capabilities":{
   "lookup":{"owner":"agent","add":["order_found"]},
   "refund":{"owner":"agent","pre":"order_found","add":["refunded"]},
   "update_ledger":{"owner":"agent","pre":"refunded","add":["ledger_updated"]}},
 "protocol":[{"act":{"cap":"lookup","by":"agent"}},
             {"act":{"cap":"refund","by":"agent"}},
             {"act":{"cap":"update_ledger","by":"agent"}}],
 "goal":{"and":["refunded","ledger_updated"]}},
 note="environment omits the required update_ledger grant",
 environment_grants=["lookup", "refund"])

# ---------------------------------------------- SPURIOUS (T3 incompleteness)
add("spurious_payload", "SPURIOUS", "IMPOSSIBLE",
"""
# Skill: Book a flight under $500
Goal: booked under 500 and confirmed.
Tools: search, filter_cheap, book, email.
The filter_cheap tool keeps only fares under 500.
Plan: search, filter, book, then email the confirmation.
""",
{"name":"spurious_payload","roles":["agent"],
 "capabilities":{
   "search":{"owner":"agent","add":["searched"]},
   # compaction trusts the declared post-condition price<500 (payload faithfulness
   # is NOT verified by Layer A) -> abstraction admits a satisfying price
   "filter_cheap":{"owner":"agent","pre":"searched","add":["filtered"],
                   "nondet":{"price":{"cmp":["price","<",500]}}},
   "book":{"owner":"agent","pre":"filtered","add":["booked"]},
   "email":{"owner":"agent","pre":"booked","add":["confirmation_sent"]}},
 "protocol":[{"act":{"cap":"search","by":"agent"}},
             {"act":{"cap":"filter_cheap","by":"agent"}},
             {"act":{"cap":"book","by":"agent"}},
             {"act":{"cap":"email","by":"agent"}}],
 "goal":{"and":["booked","confirmation_sent",{"cmp":["price","<",500]}]}},
 note="FALSE ACHIEVABLE: payload faithfulness of filter_cheap is a Layer-C "
      "(runtime) obligation, not decided here. Expected incompleteness.")

add("spurious_intent", "SPURIOUS", "IMPOSSIBLE",
"""
# Skill: Schedule a meeting
The user asks for a meeting with the right attendees next week.
Goal: the meeting is scheduled.
Tool: create_event.
Plan: create the calendar event for next week.
""",
{"name":"spurious_intent","roles":["agent"],
 "capabilities":{
   "create_event":{"owner":"agent","add":["meeting_scheduled"]}},
 "protocol":[{"act":{"cap":"create_event","by":"agent"}}],
 "goal":"meeting_scheduled"},
 note="FALSE ACHIEVABLE: intent fidelity (does the formal goal capture what the "
      "user meant) is the top-edge residue, surfaced for human review, not decided.")

# A couple more straightforward ACHIEVABLE/IMPOSSIBLE for balance
add("recursion_ok", "ACHIEVABLE", "ACHIEVABLE",
"""
# Skill: Retry search until found, then answer
Goal: answer delivered. search may be tried; once found, deliver.
""",
{"name":"recursion_ok","roles":["worker"],
 "capabilities":{
   "search":{"owner":"worker","add":["found"]},
   "deliver":{"owner":"worker","pre":"found","add":["answered"]}},
 "protocol":[{"act":{"cap":"search","by":"worker"}},
             {"act":{"cap":"deliver","by":"worker"}}],
 "goal":"answered"})

add("two_goals_one_missing", "HALLUCINATED_PLANNING", "IMPOSSIBLE",
"""
# Skill: Onboard employee
Goal: account created AND badge issued.
Required tools: create_account, issue_badge.
Plan: create the employee account, then issue the employee badge.
""",
{"name":"two_goals_one_missing","roles":["agent"],
 "capabilities":{
   "create_account":{"owner":"agent","add":["account_created"]},
   "issue_badge":{"owner":"agent","pre":"account_created","add":["badge_issued"]}},
 "protocol":[{"act":{"cap":"create_account","by":"agent"}},
             {"act":{"cap":"issue_badge","by":"agent"}}],
 "goal":{"and":["account_created","badge_issued"]}},
 note="environment omits the required issue_badge grant",
 environment_grants=["create_account"])

add("choice_one_branch_ok", "TOLERANCE", "ACHIEVABLE",
"""
# Skill: Pay invoice by card or transfer
Goal: invoice paid.
The system chooses card or transfer, tells the payer which rail to use, and the
payer completes the selected payment.
""",
{"name":"choice_one_branch_ok","roles":["sys","payer"],
 "capabilities":{
   "pay_card":{"owner":"payer","add":["paid"]},
   "pay_transfer":{"owner":"payer","add":["paid"]}},
 "protocol":[{"choice":{"by":"sys","branches":{
     "card":[{"msg":{"from":"sys","to":"payer","label":"use_card"}},
             {"act":{"cap":"pay_card","by":"payer"}}],
     "transfer":[{"msg":{"from":"sys","to":"payer","label":"use_transfer"}},
                 {"act":{"cap":"pay_transfer","by":"payer"}}]}}}],
 "goal":"paid"})

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "src", "skillc", "data", "corpus.json")
with open(OUT, "w") as f:
    json.dump(C, f, indent=2)
print(f"wrote {os.path.relpath(OUT)} with {len(C)} specs")
print("by category:", dict(Counter(c["category"] for c in C)))
print("by ground truth:", dict(Counter(c["ground_truth"] for c in C)))

# ==========================================================================
# Extended corpus: the decidable-fragment boundary (tail recursion, dynamic
# spawning) and the conformance premise.  Kept separate from the 15-spec
# headline corpus so the paper's confusion matrix stays reproducible.
# Ground truth may be UNKNOWN: outside the fragment the semi-decision must
# neither claim ACHIEVABLE nor IMPOSSIBLE.
# ==========================================================================

E = []

def add_ext(id, category, ground_truth, nl, pack, note="",
            environment_grants=None, input_type="skill"):
    E.append({"id": id, "category": category, "ground_truth": ground_truth,
              "nl": nl.strip(), "pack": pack, "note": note,
              "environment_grants": (
                  list(pack["capabilities"])
                  if environment_grants is None else environment_grants),
              "input_type": input_type})

add_ext("retry_loop_ok", "TOLERANCE", "ACHIEVABLE",
"""
# Skill: Retry search until found, then deliver
Goal: answer delivered. Search in a loop; when found, exit and deliver.
""",
{"name":"retry_loop_ok","roles":["worker"],
 "capabilities":{
   "search":{"owner":"worker","add":["found"]},
   "deliver":{"owner":"worker","pre":"found","add":["answered"]}},
 "protocol":[{"rec":{"name":"X","body":[
                {"act":{"cap":"search","by":"worker"}},
                {"choice":{"by":"worker","branches":{
                  "retry":[{"continue":"X"}],
                  "found":[]}}}]}},
             {"act":{"cap":"deliver","by":"worker"}}],
 "goal":"answered"},
 note="tail-recursive retry with an exit branch is inside the fragment")

add_ext("spin_forever", "INFINITE_LOOP", "IMPOSSIBLE",
"""
# Skill: Publish a report
Goal: published.
Required tools: draft, publish.
Plan: repeatedly draft and review the report without reaching the publish step.
""",
{"name":"spin_forever","roles":["agent"],
 "capabilities":{
   "draft":{"owner":"agent","add":["drafted"]},
   "publish":{"owner":"agent","pre":"drafted","add":["published"]}},
 "protocol":[{"rec":{"name":"X","body":[
                {"act":{"cap":"draft","by":"agent"}},
                {"continue":"X"}]}}],
 "goal":"published"},
 note="predicate-state saturation terminates the loop search -> GOAL_UNSAT")

add_ext("spawn_helpers", "AUTONOMY", "UNKNOWN",
"""
# Skill: Fan out research to freshly spawned subagents
Goal: report delivered. The planner spawns helper agents at run time.
""",
{"name":"spawn_helpers","roles":["planner"],
 "capabilities":{"deliver":{"owner":"planner","add":["delivered"]}},
 "protocol":[{"spawn":{"role":"helper"}},
             {"act":{"cap":"deliver","by":"planner"}}],
 "goal":"delivered"},
 note="dynamic topology -> outside the decidable fragment (thm:undec)")

add_ext("spawn_with_ghost_tool", "AUTONOMY", "IMPOSSIBLE",
"""
# Skill: Fan out, then update the ledger
Goal: ledger updated.
Required tool: update_ledger.
Plan: spawn helpers, collect their work, then update the ledger.
""",
{"name":"spawn_with_ghost_tool","roles":["planner"],
 "capabilities":{
   "update_ledger":{"owner":"planner","add":["ledger_updated"]}},
 "protocol":[{"spawn":{"role":"helper"}},
             {"act":{"cap":"update_ledger","by":"planner"}}],
 "goal":"ledger_updated"},
 note="environment omits update_ledger; capability refutation precedes autonomy",
 environment_grants=[])

add_ext("nonconformant_handler", "CONFORMANCE", "IMPOSSIBLE",
"""
# Skill: Triage then handle
Goal: resolved.
The router may send go_simple or go_complex. The declared handler behaviour
waits for go_simple and then resolves the ticket.
""",
{"name":"nonconformant_handler","roles":["router","handler"],
 "capabilities":{
   "resolve_simple":{"owner":"handler","add":["resolved"]},
   "resolve_complex":{"owner":"handler","add":["resolved"]}},
 "protocol":[{"choice":{"by":"router","branches":{
     "simple":[{"msg":{"from":"router","to":"handler","label":"go_simple"}},
               {"act":{"cap":"resolve_simple","by":"handler"}}],
     "complex":[{"msg":{"from":"router","to":"handler","label":"go_complex"}},
                {"act":{"cap":"resolve_complex","by":"handler"}}]}}}],
 "goal":"resolved",
 "skills":{"handler":[{"branch":{"from":"router","branches":{
     "go_simple":[{"act":{"cap":"resolve_simple"}}]}}}]}},
 note="S_handler drops an external choice -> S </= G|handler (Sub-Ext)")

add_ext("conformant_tolerant_handler", "CONFORMANCE", "ACHIEVABLE",
"""
# Skill: Triage then handle
Goal: resolved.
The router may send go_simple or go_complex. The declared handler accepts
go_simple, go_complex, or go_escalate.
""",
{"name":"conformant_tolerant_handler","roles":["router","handler"],
 "capabilities":{
   "resolve_simple":{"owner":"handler","add":["resolved"]},
   "resolve_complex":{"owner":"handler","add":["resolved"]}},
 "protocol":[{"choice":{"by":"router","branches":{
     "simple":[{"msg":{"from":"router","to":"handler","label":"go_simple"}},
               {"act":{"cap":"resolve_simple","by":"handler"}}],
     "complex":[{"msg":{"from":"router","to":"handler","label":"go_complex"}},
                {"act":{"cap":"resolve_complex","by":"handler"}}]}}}],
 "goal":"resolved",
 "skills":{"handler":[{"branch":{"from":"router","branches":{
     "go_simple":[{"act":{"cap":"resolve_simple"}}],
     "go_complex":[{"act":{"cap":"resolve_complex"}}],
     "go_escalate":[{"act":{"cap":"resolve_complex"}}]}}}]}},
 note="interface slack in the safe direction must not refute (T2 flavour)")

add_ext("choice_uninformed_alert", "NON_PROJECTABLE", "IMPOSSIBLE",
"""
# Skill: Route an alert
Goal: the alert is handled.
Required tools: handle_now, handle_later.
The monitor privately chooses urgent or routine. The oncall must handle urgent
alerts now and routine alerts later, but receives no branch label.
""",
{"name":"choice_uninformed_alert","roles":["monitor","oncall"],
 "capabilities":{
   "handle_now":{"owner":"oncall","add":["handled"]},
   "handle_later":{"owner":"oncall","add":["handled"]}},
 "protocol":[{"choice":{"by":"monitor","branches":{
   "urgent":[{"act":{"cap":"handle_now","by":"oncall"}}],
   "routine":[{"act":{"cap":"handle_later","by":"oncall"}}]}}}],
 "goal":"handled"},
 note="the acting role cannot observe which branch the monitor selected")

add_ext("selector_drops_branch", "CONFORMANCE", "IMPOSSIBLE",
"""
# Agent: Route a ticket
Goal: the ticket is resolved.
Required tools: fix_a, fix_b.
The contract permits routes A and B and notifies the handler with go_a or
go_b. The router agent declares only route A.
""",
{"name":"selector_drops_branch","roles":["router","handler"],
 "capabilities":{
   "fix_a":{"owner":"handler","add":["resolved"]},
   "fix_b":{"owner":"handler","add":["resolved"]}},
 "protocol":[{"choice":{"by":"router","branches":{
   "a":[{"msg":{"from":"router","to":"handler","label":"go_a"}},
        {"act":{"cap":"fix_a","by":"handler"}}],
   "b":[{"msg":{"from":"router","to":"handler","label":"go_b"}},
        {"act":{"cap":"fix_b","by":"handler"}}]}}}],
 "goal":"resolved",
 "skills":{"router":[{"select":{"branches":{
   "a":[{"send":{"to":"handler","label":"go_a"}}]}}}]}},
 note="the declared sender behavior omits a contract branch",
 input_type="agent")

add_ext("selector_invents_label", "CONFORMANCE", "IMPOSSIBLE",
"""
Prompt: Resolve a routed ticket.
Required tools: fix_a, fix_b.
The protocol permits go_a and go_b. The router implementation instead selects
go_c, which is not a protocol label.
""",
{"name":"selector_invents_label","roles":["router","handler"],
 "capabilities":{
   "fix_a":{"owner":"handler","add":["resolved"]},
   "fix_b":{"owner":"handler","add":["resolved"]}},
 "protocol":[{"choice":{"by":"router","branches":{
   "a":[{"msg":{"from":"router","to":"handler","label":"go_a"}},
        {"act":{"cap":"fix_a","by":"handler"}}],
   "b":[{"msg":{"from":"router","to":"handler","label":"go_b"}},
        {"act":{"cap":"fix_b","by":"handler"}}]}}}],
 "goal":"resolved",
 "skills":{"router":[{"select":{"branches":{
   "c":[{"send":{"to":"handler","label":"go_c"}}]}}}]}},
 note="the declared sender behavior invents a label outside the protocol",
 input_type="prompt")

OUT_EXT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "..", "src", "skillc", "data", "corpus_extended.json")
with open(OUT_EXT, "w") as f:
    json.dump(E, f, indent=2)
print(f"wrote {os.path.relpath(OUT_EXT)} with {len(E)} extended specs")
