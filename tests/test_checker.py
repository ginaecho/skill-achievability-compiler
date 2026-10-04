"""Verdict-level tests of the trusted checker, one per refutation reason,
plus the tolerance behaviours and the T3 (cap monotonicity) property."""
import pytest

from skillc import check
from skillc.checker import SOLVER_TIMEOUT_MS
from skillc.evaluate import load_corpus
from skillc.pack import Capability, Pack, PackError, pack_digest


def pack(**kw):
    base = {"name": "t", "roles": ["agent"], "capabilities": {},
            "protocol": [], "goal": True}
    base.update(kw)
    return base


def act(cap, by="agent"):
    return {"act": {"cap": cap, "by": by}}


def test_trivial_goal_achievable():
    v = check(pack())
    assert v.achievable and v.label == "ACHIEVABLE"


def test_linear_chain_achievable_with_witness():
    v = check(pack(
        capabilities={
            "search": {"add": ["searched"]},
            "book": {"pre": "searched", "add": ["booked"]}},
        protocol=[act("search"), act("book")],
        goal="booked"))
    assert v.achievable
    assert v.witness == (("act", "search"), ("act", "book"))


def test_missing_capability():
    v = check(pack(
        capabilities={"search": {"add": ["searched"]}},
        protocol=[act("search"), act("send_email")],
        goal="searched"))
    assert not v.achievable
    assert v.reason == "MISSING_CAPABILITY"
    assert v.frontier == ("send_email",)


def test_goal_only_abstains_when_missing_action_is_not_goal_essential():
    p = pack(capabilities={"finish": {"add": ["done"]}},
             protocol=[act("finish"), act("cleanup")], goal="done")
    assert check(p).reason == "MISSING_CAPABILITY"
    result = check(p, scope="goal")
    assert result.label == "UNKNOWN"
    assert result.reason == "PROTOCOL_ONLY"
    assert not result.context_refuted


def test_goal_only_rejects_missing_essential_capability_with_context_certificate():
    p = pack(capabilities={"read": {"add": ["read"]}},
             protocol=[act("read"), act("publish")], goal="published")
    result = check(p, scope="goal")
    assert result.refuted and result.context_refuted
    assert result.to_dict()["refutation_scope"] == "capability_context"
    assert result.to_dict()["decision_scope"] == "goal"


def test_goal_only_rejects_adversarial_semantics():
    with pytest.raises(ValueError, match="may"):
        check(pack(), semantics="adversarial", scope="goal")


def test_goal_only_proves_permanently_blocked_guard_without_rejecting_repair():
    p = pack(capabilities={
        "publish": {"pre": "authorized", "add": ["published"]}},
        protocol=[act("publish")], goal="published")
    assert check(p, scope="goal").context_refuted
    p["capabilities"]["authorize"] = {"add": ["authorized"]}
    result = check(p, scope="goal")
    assert result.unknown and not result.refuted


def test_goal_guard_closure_is_conservative_for_negative_preconditions():
    p = pack(capabilities={
        "finish": {"pre": {"not": "blocked"}, "add": ["done"]},
        "block": {"add": ["blocked"]}},
        protocol=[act("finish")], goal="done")
    assert check(p, scope="goal").achievable


def test_context_certificate_separates_predicates_from_numeric_placeholders():
    p = pack(init_true=["__cmp_0"], goal={
        "and": ["__cmp_0", {"not": {"cmp": [0, "==", 1]}}]})
    assert check(p).achievable
    assert check(p, scope="goal").achievable


def test_goal_unsat_no_establisher():
    # STRIPS frame: confirmation_sent is false unless some effect adds it.
    v = check(pack(
        capabilities={"book": {"add": ["booked"]}},
        protocol=[act("book")],
        goal={"and": ["booked", "confirmation_sent"]}))
    assert not v.achievable
    assert v.reason == "GOAL_UNSAT"


def test_blocked_guard():
    v = check(pack(
        capabilities={
            "draft": {"add": ["drafted"]},
            "publish": {"pre": {"and": ["drafted", "approved"]},
                        "add": ["published"]}},
        protocol=[act("draft"), act("publish")],
        goal="published"))
    assert not v.achievable
    assert v.reason == "BLOCKED_GUARD"
    assert "publish" in v.detail


def test_non_projectable_unobserved_choice():
    v = check(pack(
        roles=["planner", "worker"],
        capabilities={
            "answer": {"add": ["answered"]},
            "deliver": {"pre": "answered", "add": ["delivered"]},
            "deliver_direct": {"add": ["delivered"]}},
        protocol=[{"choice": {"by": "worker", "branches": {
            "ask": [act("answer", "planner"), act("deliver", "worker")],
            "direct": [act("deliver_direct", "worker")]}}}],
        goal="delivered"))
    assert not v.achievable
    assert v.reason == "NON_PROJECTABLE"
    assert "planner" in v.detail


def test_informed_choice_is_projectable_and_achievable():
    v = check(pack(
        roles=["router", "handler"],
        capabilities={
            "fix_a": {"add": ["resolved"]},
            "fix_b": {"add": ["resolved"]}},
        protocol=[{"choice": {"by": "router", "branches": {
            "a": [{"msg": {"from": "router", "to": "handler", "label": "go_a"}},
                  act("fix_a", "handler")],
            "b": [{"msg": {"from": "router", "to": "handler", "label": "go_b"}},
                  act("fix_b", "handler")]}}}],
        goal="resolved"))
    assert v.achievable
    assert ("choose", "a") in v.witness or ("choose", "b") in v.witness


def test_choice_is_existential_one_good_branch_suffices():
    v = check(pack(
        capabilities={"win": {"add": ["done"]}, "noop": {}},
        protocol=[{"choice": {"by": "agent", "branches": {
            "bad": [act("noop")],
            "good": [act("win")]}}}],
        goal="done"))
    assert v.achievable


def test_budget_refinement_satisfiable():
    v = check(pack(
        capabilities={"book": {"add": ["booked"],
                               "nondet": {"price": {"cmp": ["price", "<", 500]}}}},
        protocol=[act("book")],
        goal={"and": ["booked", {"cmp": ["price", "<", 500]}]}))
    assert v.achievable


def test_budget_refinement_unsatisfiable_on_every_run():
    v = check(pack(
        capabilities={"book": {"add": ["booked"],
                               "nondet": {"price": {"cmp": ["price", ">=", 800]}}}},
        protocol=[act("book")],
        goal={"and": ["booked", {"cmp": ["price", "<", 500]}]}))
    assert not v.achievable
    assert v.reason == "GOAL_UNSAT"


def test_deterministic_assign_and_arithmetic():
    v = check(pack(
        capabilities={
            "init": {"assigns": {"x": 3}, "add": ["started"]},
            "double": {"assigns": {"x": {"*": [2, "x"]}}}},
        protocol=[act("init"), act("double")],
        goal={"and": ["started", {"cmp": ["x", "==", 6]}]}))
    assert v.achievable


def test_delete_effect_and_frame():
    v = check(pack(
        capabilities={
            "grab": {"add": ["holding"]},
            "drop": {"pre": "holding", "del": ["holding"]}},
        protocol=[act("grab"), act("drop")],
        goal="holding"))
    assert not v.achievable
    assert v.reason == "GOAL_UNSAT"


def test_add_then_delete_matches_world_act_order():
    v = check(pack(
        capabilities={"toggle": {"add": ["holding"], "del": ["holding"]}},
        protocol=[act("toggle")],
        goal={"not": "holding"}))
    assert v.achievable


def test_deterministic_assignment_precedes_overlapping_nondet_update():
    v = check(pack(
        capabilities={"set": {
            "assigns": {"x": 1},
            "nondet": {"x": {"cmp": ["x", "==", 2]}}}},
        protocol=[act("set")],
        goal={"cmp": ["x", "==", 1]}))
    assert v.achievable


def test_nondeterministic_updates_are_simultaneous():
    v = check(pack(
        capabilities={"swap": {"nondet": {
            "x": {"cmp": ["x", "==", "y"]},
            "y": {"cmp": ["y", "==", "x"]}}}},
        protocol=[act("swap")],
        init_constraints=[
            {"cmp": ["x", "==", 0]},
            {"cmp": ["y", "==", 1]}],
        goal={"and": [
            {"cmp": ["x", "==", 1]},
            {"cmp": ["y", "==", 0]}]}))
    assert v.achievable


def test_action_with_empty_nondeterministic_effect_relation_is_blocked():
    v = check(pack(
        capabilities={"impossible": {"nondet": {"x": False}}},
        protocol=[act("impossible")],
        goal=True))
    assert v.refuted
    assert v.reason == "BLOCKED_GUARD"
    assert "no successor world" in v.detail


def test_goal_marker_midway():
    v = check(pack(
        capabilities={"a": {"add": ["done"]}, "b": {"del": ["done"]}},
        protocol=[act("a"), {"goal": "done"}, act("b")],
        goal="done"))
    assert v.achievable        # goal observed at the marker, before b undoes it


def test_unsatisfied_goal_marker_blocks_later_achievement():
    v = check(pack(
        capabilities={"finish": {"add": ["done"]}},
        protocol=[{"goal": "done"}, act("finish")],
        goal="done"))
    assert v.refuted
    assert v.reason == "GOAL_UNSAT"


def test_direct_typing_checks_every_choice_branch_at_one_initial_world():
    v = check(pack(
        capabilities={
            "zero": {"pre": {"cmp": ["x", "==", 0]}, "add": ["done"]},
            "one": {"pre": {"cmp": ["x", "==", 1]}, "add": ["done"]}},
        protocol=[{"choice": {"by": "agent", "branches": {
            "zero": [act("zero")],
            "one": [act("one")]}}}],
        goal="done"))
    assert v.refuted
    assert v.reason == "NON_CONFORMANT"
    assert "same initial world" in v.detail


def test_direct_typing_checks_goal_marker_on_every_choice_branch():
    v = check(pack(
        capabilities={"finish": {"add": ["done"]}},
        protocol=[{"choice": {"by": "agent", "branches": {
            "valid": [act("finish"), {"goal": "done"}],
            "invalid": [{"goal": "done"}]}}}],
        goal="done"))
    assert v.refuted
    assert v.reason == "NON_CONFORMANT"


def test_terminal_goal_and_conformance_share_initial_world():
    v = check(pack(
        capabilities={
            "finish": {"add": ["done"]},
            "require_one": {"pre": {"cmp": ["x", "==", 1]},
                            "add": ["done"]}},
        protocol=[{"choice": {"by": "agent", "branches": {
            "first": [act("finish")],
            "second": [act("require_one")]}}}],
        goal={"and": ["done", {"cmp": ["x", "==", 0]}]}))
    assert v.refuted
    assert v.reason == "NON_CONFORMANT"


def test_joint_typing_search_tries_another_goal_witness():
    v = check(pack(
        capabilities={
            "finish": {"add": ["done"]},
            "repair": {"pre": {"cmp": ["x", "==", 1]},
                       "assigns": {"x": 0}, "add": ["done"]}},
        protocol=[{"choice": {"by": "agent", "branches": {
            "first": [act("finish")],
            "second": [act("repair")]}}}],
        goal={"and": ["done", {"cmp": ["x", "==", 0]}]}))
    assert v.achievable
    assert ("choose", "second") in v.witness


def test_guard_is_retained_in_reachability_path_condition():
    v = check(pack(
        capabilities={"a": {
            "pre": {"cmp": ["x", "==", 0]},
            "add": ["done"]}},
        protocol=[act("a")],
        goal={"and": ["done", {"cmp": ["x", "==", 5]}]}))
    assert v.refuted
    assert v.reason == "GOAL_UNSAT"


def test_detour_messages_do_not_refute():
    v = check(pack(
        roles=["worker", "user"],
        capabilities={"do": {"add": ["done"]}},
        protocol=[{"msg": {"from": "worker", "to": "user", "label": "status"}},
                  act("do", "worker"),
                  {"msg": {"from": "worker", "to": "user", "label": "status2"}}],
        goal="done"))
    assert v.achievable


def test_init_true_and_init_constraints():
    v = check(pack(
        capabilities={"spend": {"pre": "funded",
                                "assigns": {"balance": {"-": ["balance", 100]}}}},
        protocol=[act("spend")],
        goal={"cmp": ["balance", ">=", 0]},
        init_true=["funded"],
        init_constraints=[{"cmp": ["balance", "==", 100]}]))
    assert v.achievable


def test_cap_monotone_on_corpus():
    """Coq T3 operational check: adding a fresh capability to any corpus pack
    never turns ACHIEVABLE into IMPOSSIBLE."""
    for c in load_corpus():
        before = check(c["pack"]).achievable
        widened = dict(c["pack"])
        widened["capabilities"] = dict(widened["capabilities"],
                                       extra_cap={"add": ["extra_pred"]})
        after = check(widened).achievable
        if before:
            assert after, f"cap_monotone violated on {c['id']}"


# --------------------------------------------------------------------------
# UNKNOWN is an abstention, not a refutation
# --------------------------------------------------------------------------

SPAWN_PACK = {"name": "spawner", "capabilities": {},
              "protocol": [{"spawn": {"role": "helper"}}], "goal": True}


def test_unknown_verdict_is_not_a_refutation():
    v = check(SPAWN_PACK)
    assert v.label == "UNKNOWN"
    assert v.unknown and not v.achievable
    assert not v.refuted, "UNKNOWN must never count as a refutation"


def test_refuted_is_true_only_for_definite_impossible():
    impossible = check(pack(
        capabilities={"book": {"add": ["booked"]}},
        protocol=[act("book")],
        goal={"and": ["booked", "confirmation_sent"]}))
    assert impossible.refuted and not impossible.unknown
    assert not check(pack()).refuted


def test_verdict_dict_reports_unknown_and_refuted_explicitly():
    d = check(SPAWN_PACK).to_dict()
    assert d["verdict"] == "UNKNOWN"
    assert d["unknown"] is True and d["refuted"] is False


# --------------------------------------------------------------------------
# The check() seam validates dicts AND Pack objects
# --------------------------------------------------------------------------

def test_check_accepts_a_well_formed_pack_object():
    d = pack(capabilities={"a": {"add": ["done"]}},
             protocol=[act("a")], goal="done")
    from_dict = check(d)
    from_obj = check(Pack.load(d))
    assert from_obj.achievable and from_obj.label == from_dict.label
    assert from_obj.witness == from_dict.witness


def test_malformed_pack_object_cannot_bypass_the_schema_gate():
    bad_goal = Pack(name="t", roles=[], capabilities={},
                    protocol=[], goal={"cmp": ["x", "~", 1]})
    with pytest.raises(PackError):
        check(bad_goal)


def test_malformed_capability_in_pack_object_is_rejected():
    bad_cap = Pack(name="t", roles=[],
                   capabilities={"a": Capability(name="a", pre={"nand": []})},
                   protocol=[], goal=True)
    with pytest.raises(PackError):
        check(bad_cap)


def test_untyped_capability_in_pack_object_is_rejected():
    untyped = Pack(name="t", roles=[], capabilities={"a": {"add": ["done"]}},
                   protocol=[], goal="done")
    with pytest.raises(PackError):
        check(untyped)


def test_check_rejects_non_pack_input():
    with pytest.raises(PackError):
        check("not a pack")


# --------------------------------------------------------------------------
# QF-LIA: no variable * variable; the solver has a finite budget
# --------------------------------------------------------------------------

def test_nonlinear_multiplication_is_rejected_at_the_gate():
    with pytest.raises(PackError, match="QF-LIA"):
        check(pack(
            capabilities={"a": {"assigns": {"x": {"*": ["x", "y"]}}}},
            protocol=[act("a")],
            goal={"cmp": ["x", ">", 0]}))


def test_nonlinear_goal_is_rejected_at_the_gate():
    with pytest.raises(PackError, match="QF-LIA"):
        check(pack(goal={"cmp": [{"*": ["x", "y"]}, ">", 0]}))


def test_linear_multiplication_still_checks():
    v = check(pack(
        capabilities={"init": {"assigns": {"x": 3}},
                      "scale": {"assigns": {"x": {"*": ["x", 4]}}}},
        protocol=[act("init"), act("scale")],
        goal={"cmp": ["x", "==", 12]}))
    assert v.achievable


def test_solver_budget_is_finite():
    assert isinstance(SOLVER_TIMEOUT_MS, int) and 0 < SOLVER_TIMEOUT_MS


def test_every_solver_query_gets_the_budget(monkeypatch):
    import z3
    seen = []
    original = z3.Solver.set
    monkeypatch.setattr(z3.Solver, "set",
                        lambda self, *a, **kw: (seen.append(a), original(self, *a, **kw))[1])
    check(pack(capabilities={"a": {"add": ["done"]}},
               protocol=[act("a")], goal="done"))
    assert seen and all(a == ("timeout", SOLVER_TIMEOUT_MS) for a in seen)


def test_solver_unknown_never_refutes_and_is_reported(monkeypatch):
    """A solver that cannot decide must not produce a refutation: the
    normally-IMPOSSIBLE pack degrades to ACHIEVABLE with the approximation
    stated in the detail, never to a false IMPOSSIBLE."""
    import z3
    monkeypatch.setattr(z3.Solver, "check", lambda self, *a: z3.unknown)
    v = check(pack(capabilities={"book": {"add": ["booked"]}},
                   protocol=[act("book")],
                   goal={"and": ["booked", "confirmation_sent"]}))
    assert v.achievable and not v.refuted
    assert "solver returned unknown" in v.detail


# --------------------------------------------------------------------------
# Self-describing verdicts
# --------------------------------------------------------------------------

def test_verdict_dict_is_self_describing():
    from skillc import __version__
    d = check(pack(capabilities={"a": {"add": ["done"]}},
                   protocol=[act("a")], goal="done")).to_dict()
    assert d["semantics"] == "may"
    assert d["skillc_version"] == __version__
    assert d["pack_digest"].startswith("sha256:")
    assert d["deferred_obligations"] == [
        "intent_fidelity", "payload_faithfulness"]


def test_only_achievable_verdicts_carry_deferred_obligations():
    impossible = check(pack(
        protocol=[act("missing")],
        goal=True))
    assert impossible.to_dict()["deferred_obligations"] == []
    assert check(SPAWN_PACK).to_dict()["deferred_obligations"] == []


def test_verdict_records_the_semantics_it_was_decided_under():
    d = pack(capabilities={"a": {"add": ["done"]}},
             protocol=[act("a")], goal="done")
    assert check(d, semantics="adversarial").to_dict()["semantics"] == "adversarial"


def test_pack_digest_is_deterministic_across_dict_and_object():
    d = pack(capabilities={"a": {"add": ["done"]}},
             protocol=[act("a")], goal="done")
    assert check(d).pack_digest == check(Pack.load(d)).pack_digest
    assert check(d).pack_digest == pack_digest(d)
    other = dict(d, goal="something_else")
    assert check(d).pack_digest != check(other).pack_digest
