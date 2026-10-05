"""Environment tool contracts replace an intent's assumed tool behaviour."""
from skillc import check
from skillc.frontend.contracts import apply_contracts, bind_environment


def _pack(goal, capabilities, protocol):
    return {
        "name": "t", "roles": ["agent"], "capabilities": capabilities,
        "protocol": [{"act": {"cap": name, "by": "agent"}} for name in protocol],
        "goal": goal,
    }


ASSUMED_BOOKING = {
    "search": {"owner": "agent", "add": ["searched"]},
    "book_fare": {"owner": "agent", "pre": "searched", "add": ["booked"],
                  "nondet": {"price": {"cmp": ["price", "<", 500]}}},
    "email": {"owner": "agent", "pre": "booked", "add": ["confirmation_sent"]},
}
STATES = {"searched": "", "booked": "", "confirmation_sent": "", "price": "",
          "drafted": "", "approved": "", "published": "", "notification_queued": ""}


def test_environment_price_contract_refutes_an_intent_budget():
    pack = _pack({"and": ["booked", {"cmp": ["price", "<", 500]}]},
                 ASSUMED_BOOKING, ["search", "book_fare"])
    contracts = {"book_fare": {"pre": "searched", "add": ["booked"],
                               "nondet": {"price": {"cmp": ["price", ">=", 800]}}}}

    binding = apply_contracts(pack, contracts, STATES)

    assert binding.applied == ("book_fare",)
    assert binding.pack["capabilities"]["book_fare"]["owner"] == "agent"
    assert check(binding.pack).reason == "GOAL_UNSAT"


def test_environment_effect_contract_removes_an_assumed_establisher():
    pack = _pack({"and": ["booked", "confirmation_sent"]},
                 {**ASSUMED_BOOKING,
                  "notify": {"owner": "agent", "pre": "booked", "add": ["confirmation_sent"]}},
                 ["search", "book_fare", "notify"])
    contracts = {"notify": {"pre": "booked", "add": ["notification_queued"]}}

    verdict = check(apply_contracts(pack, contracts, STATES).pack)

    assert verdict.reason == "GOAL_UNSAT"


def test_environment_precondition_no_tool_establishes_blocks_the_plan():
    pack = _pack("published",
                 {"draft": {"owner": "agent", "add": ["drafted"]},
                  "publish": {"owner": "agent", "pre": "drafted", "add": ["published"]}},
                 ["draft", "publish"])
    contracts = {"draft": {"add": ["drafted"]},
                 "publish": {"pre": {"and": ["drafted", "approved"]}, "add": ["published"]}}

    verdict = check(apply_contracts(pack, contracts, STATES).pack)

    assert verdict.reason == "BLOCKED_GUARD"


def test_matching_contracts_keep_an_achievable_intent_achievable():
    pack = _pack({"and": ["booked", "confirmation_sent"]}, ASSUMED_BOOKING,
                 ["search", "book_fare", "email"])
    contracts = {name: {k: v for k, v in cap.items() if k != "owner"}
                 for name, cap in ASSUMED_BOOKING.items()}

    assert check(apply_contracts(pack, contracts, STATES).pack).achievable


def test_goal_outside_the_environment_vocabulary_leaves_the_pack_unchanged():
    pack = _pack({"and": ["booked", "sent"]}, ASSUMED_BOOKING, ["search", "book_fare"])
    contracts = {"book_fare": {"add": ["booked"],
                               "nondet": {"price": {"cmp": ["price", ">=", 800]}}}}

    binding = apply_contracts(pack, contracts, STATES)

    assert binding.applied == ()
    assert binding.unaligned == ("sent",)
    assert binding.pack == pack


def test_capabilities_without_a_contract_keep_the_intent_definition():
    pack = _pack("booked", ASSUMED_BOOKING, ["search", "book_fare"])

    binding = apply_contracts(pack, {"search": {"add": ["searched"]}}, STATES)

    assert binding.applied == ("search",)
    assert binding.pack["capabilities"]["book_fare"] == ASSUMED_BOOKING["book_fare"]


def test_environment_initial_state_satisfies_contract_preconditions():
    pack = _pack("published",
                 {"publish": {"owner": "agent", "add": ["published"]}}, ["publish"])
    contracts = {"publish": {"pre": "approved", "add": ["published"]}}

    without = check(apply_contracts(pack, contracts, STATES).pack)
    with_init = check(apply_contracts(pack, contracts, STATES, init_true=["approved"]).pack)

    assert without.reason == "BLOCKED_GUARD"
    assert with_init.achievable


def test_bind_environment_withholds_tools_then_applies_contracts():
    pack = _pack({"and": ["booked", "confirmation_sent"]}, ASSUMED_BOOKING,
                 ["search", "book_fare", "email"])
    manifest = {"contracts": {"book_fare": {"pre": "searched", "add": ["queued"]}},
                "states": {**STATES, "queued": ""}}

    binding = bind_environment(pack, ["search", "book_fare"], manifest)

    assert binding.unavailable == ("email",)
    assert binding.contracts_applied == ("book_fare",)
    assert check(binding.pack).reason == "MISSING_CAPABILITY"


def _refutation(reason, frontier):
    from skillc.checker import Verdict
    return Verdict(False, reason, "detail", frontier=tuple(frontier))


def test_refutation_resting_only_on_undefined_conditions_abstains():
    from skillc.frontend.contracts import abstain_outside_vocabulary

    verdict = abstain_outside_vocabulary(
        _refutation("GOAL_UNSAT", ["card_selected", "transfer_selected"]), STATES)

    assert verdict.label == "UNKNOWN"
    assert verdict.reason == "UNALIGNED_CONDITION"
    assert verdict.frontier == ("card_selected", "transfer_selected")
    assert not verdict.refuted


def test_refutation_naming_an_environment_condition_stands():
    from skillc.frontend.contracts import abstain_outside_vocabulary

    for frontier in (["confirmation_sent"], ["confirmation_sent", "invented"], []):
        verdict = abstain_outside_vocabulary(_refutation("GOAL_UNSAT", frontier), STATES)
        assert verdict.label == "IMPOSSIBLE", frontier


def test_missing_capability_and_absent_vocabulary_are_untouched():
    from skillc.frontend.contracts import abstain_outside_vocabulary

    missing = _refutation("MISSING_CAPABILITY", ["send_email"])
    assert abstain_outside_vocabulary(missing, STATES) is missing
    unsat = _refutation("GOAL_UNSAT", ["invented"])
    assert abstain_outside_vocabulary(unsat, None) is unsat


def test_blocked_guard_refutations_are_never_softened():
    from skillc.frontend.contracts import abstain_outside_vocabulary

    blocked = _refutation(
        "BLOCKED_GUARD",
        ["capability 'publish' guard never satisfiable on this path (pre={'and': ['drafted', 'approved']})"])

    assert abstain_outside_vocabulary(blocked, STATES) is blocked


def test_without_vocabulary_invented_goal_conditions_abstain_when_text_lacks_them():
    from skillc.frontend.contracts import abstain_ungrounded

    invented = abstain_ungrounded(_refutation("GOAL_UNSAT", ["tests_pass"]),
                                  source_text="Fix the bug and open a pull request.")
    stated = abstain_ungrounded(_refutation("GOAL_UNSAT", ["published"]),
                                source_text="The report is published when approved.")

    assert (invented.label, invented.reason) == ("UNKNOWN", "UNALIGNED_CONDITION")
    assert stated.label == "IMPOSSIBLE"


def test_vocabulary_not_intent_wording_grounds_conditions_when_published():
    from skillc.frontend.contracts import abstain_ungrounded

    verdict = abstain_ungrounded(_refutation("GOAL_UNSAT", ["routed"]), states=STATES,
                                 source_text="Resolve the routed ticket.")

    assert verdict.label == "UNKNOWN"


def test_missing_tool_must_be_named_in_the_intent_or_extracted_from_it():
    from skillc.frontend.contracts import abstain_ungrounded

    text = "Send the summary to the team via `send_email_v2`."
    named = abstain_ungrounded(_refutation("MISSING_CAPABILITY", ["send_email_v2"]),
                               source_text=text)
    invented = abstain_ungrounded(_refutation("MISSING_CAPABILITY", ["provide_triage_plan"]),
                                  source_text=text)
    extracted = abstain_ungrounded(_refutation("MISSING_CAPABILITY", ["book_flight"]),
                                   source_text="book a flight", extracted={"book_flight"})

    assert named.label == "IMPOSSIBLE"
    assert (invented.label, invented.reason) == ("UNKNOWN", "UNGROUNDED_TOOL")
    assert extracted.label == "IMPOSSIBLE"


def test_without_any_grounding_evidence_verdicts_are_unchanged():
    from skillc.frontend.contracts import abstain_ungrounded

    for reason, frontier in (("GOAL_UNSAT", ["x"]), ("MISSING_CAPABILITY", ["y"])):
        verdict = _refutation(reason, frontier)
        assert abstain_ungrounded(verdict) is verdict


def test_blocked_guard_on_invented_precondition_abstains_but_published_one_stands():
    from skillc.frontend.contracts import abstain_ungrounded

    pack = {"capabilities": {"publish": {"owner": "agent", "pre": {"and": ["drafted", "approved"]}},
                             "write": {"owner": "agent", "pre": "fix_decided"}}}
    real = _refutation("BLOCKED_GUARD", [
        "capability 'publish' guard never satisfiable on this path (pre={'and': ['drafted', 'approved']})"])
    invented = _refutation("BLOCKED_GUARD", [
        "capability 'write' guard never satisfiable on this path (pre='fix_decided')"])

    assert abstain_ungrounded(real, states=STATES, pack=pack).label == "IMPOSSIBLE"
    result = abstain_ungrounded(invented, source_text="Fix the failing test.", pack=pack)
    assert (result.label, result.reason) == ("UNKNOWN", "UNALIGNED_CONDITION")
