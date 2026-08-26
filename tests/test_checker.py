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
