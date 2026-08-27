"""Projection (Proj-Sel/Proj-Brn/Proj-Mrg), merge, and Gay-Hole subtyping."""
import pytest

from skillc.session import (END, ProjectionError, conformance_failure,
                            conformance_report, merge, participants,
                            parse_local, project, subtype)


def act(cap, by):
    return {"act": {"cap": cap, "by": by}}


def msg(f, t, l):
    return {"msg": {"from": f, "to": t, "label": l}}


INFORMED = [{"choice": {"by": "router", "branches": {
    "a": [msg("router", "handler", "go_a"), act("fix_a", "handler")],
    "b": [msg("router", "handler", "go_b"), act("fix_b", "handler")]}}}]


class TestProjection:
    def test_selector_projects_to_select(self):
        t = project(INFORMED, "router")
        assert t[0] == "select"
        assert [l for l, _ in t[1]] == ["a", "b"]
        # inside each branch the router sends the informing label
        assert all(c[0] == "send" and c[1] == "handler" for _, c in t[1])

    def test_informed_role_projects_to_branch(self):
        t = project(INFORMED, "handler")
        assert t == ("branch", "router",
                     (("go_a", ("act", "fix_a", END)),
                      ("go_b", ("act", "fix_b", END))))

    def test_uninvolved_role_projects_to_end(self):
        assert project(INFORMED, "observer") == END

    def test_unobserved_choice_fails_with_role_named(self):
        g = [{"choice": {"by": "worker", "branches": {
            "ask": [act("answer", "planner"), act("deliver", "worker")],
            "direct": [act("deliver_direct", "worker")]}}}]
        with pytest.raises(ProjectionError, match="planner"):
            project(g, "planner")

    def test_merge_makes_identical_continuations_projectable(self):
        # planner behaves identically in both branches -> Proj-Mrg succeeds
        g = [{"choice": {"by": "worker", "branches": {
            "fast": [act("log", "planner")],
            "slow": [act("wait", "worker"), act("log", "planner")]}}}]
        assert project(g, "planner") == ("act", "log", END)

    def test_observed_choice_projects_without_messages(self):
        """Conversation-embedded choice: the medium announces the outcome
        (Proj-Obs), so no explicit msg steps are needed."""
        g = [{"choice": {"by": "business", "observed": True, "branches": {
            "confirm": [act("record", "agent")],
            "decline": [act("apologize", "agent")]}}}]
        t = project(g, "agent")
        assert t == ("branch", "business",
                     (("confirm", ("act", "record", END)),
                      ("decline", ("act", "apologize", END))))

    def test_observed_choice_uninvolved_role_stays_end(self):
        g = [{"choice": {"by": "business", "observed": True, "branches": {
            "confirm": [act("record", "agent")],
            "decline": [act("apologize", "agent")]}}}]
        assert project(g, "observer") == END

    def test_unobserved_variant_of_same_choice_fails(self):
        g = [{"choice": {"by": "business", "branches": {
            "confirm": [act("record", "agent")],
            "decline": [act("apologize", "agent")]}}}]
        with pytest.raises(ProjectionError, match="agent"):
            project(g, "agent")

    def test_projection_of_rec(self):
        g = [{"rec": {"name": "X", "body": [
            act("step", "agent"),
            {"choice": {"by": "agent", "branches": {
                "again": [{"continue": "X"}],
                "done": []}}}]}}]
        t = project(g, "agent")
        assert t[0] == "rec" and t[1] == "X"

    def test_rec_vanishes_for_uninvolved_role(self):
        g = [{"rec": {"name": "X", "body": [act("step", "agent"),
                                            {"continue": "X"}]}}]
        assert project(g, "other") == END or project(g, "other")[0] != "rec"


class TestMerge:
    def test_merge_equal(self):
        t = ("act", "a", END)
        assert merge(t, t) == t

    def test_merge_branch_label_union(self):
        a = ("branch", "p", (("l1", END),))
        b = ("branch", "p", (("l2", END),))
        assert merge(a, b) == ("branch", "p", (("l1", END), ("l2", END)))

    def test_merge_incompatible_raises(self):
        with pytest.raises(ProjectionError):
            merge(("act", "a", END), END)


class TestSubtyping:
    def test_reflexive(self):
        t = parse_local([{"send": {"to": "q", "label": "l"}},
                         {"act": {"cap": "c"}}])
        assert subtype(t, t)

    def test_sub_ext_more_external_choices_ok(self):
        contract = ("branch", "p", (("go", END),))
        skill = ("branch", "p", (("go", END), ("stop", END)))
        assert subtype(skill, contract)
        assert not subtype(contract, skill)

    def test_sub_int_fewer_internal_choices_ok(self):
        contract = ("select", (("card", END), ("transfer", END)))
        skill = ("select", (("card", END),))
        assert subtype(skill, contract)
        assert not subtype(contract, skill)

    def test_label_mismatch_fails(self):
        assert not subtype(("send", "q", "a", END), ("send", "q", "b", END))

    def test_recursive_types_coinductive(self):
        t1 = ("rec", "X", ("act", "step", ("var", "X")))
        t2 = ("rec", "Y", ("act", "step", ("var", "Y")))
        assert subtype(t1, t2)          # alpha-equivalent loops

    def test_recursive_vs_wrong_loop_fails(self):
        t1 = ("rec", "X", ("act", "step", ("var", "X")))
        t2 = ("rec", "Y", ("act", "other", ("var", "Y")))
        assert not subtype(t1, t2)


def test_parse_local_select_and_branch():
    t = parse_local([{"branch": {"from": "router", "branches": {
        "go": [{"act": {"cap": "fix"}}]}}}])
    assert t == ("branch", "router", (("go", ("act", "fix", END)),))


class TestDirectConformance:
    """`conformance_failure` decides the canonical *direct* conformance of
    T-Comm: exact sender labels, receiver-side extra branches only."""

    def test_exact_selector_conforms(self):
        assert conformance_failure(
            {"router": [{"select": {"branches": {
                "a": [{"send": {"to": "handler", "label": "go_a"}}],
                "b": [{"send": {"to": "handler", "label": "go_b"}}]}}}]},
            INFORMED) is None

    def test_selector_dropping_a_branch_is_rejected(self):
        fail = conformance_failure(
            {"router": [{"select": {"branches": {
                "a": [{"send": {"to": "handler", "label": "go_a"}}]}}}]},
            INFORMED)
        assert fail is not None and "router" in fail

    def test_selector_inventing_a_branch_is_rejected(self):
        fail = conformance_failure(
            {"router": [{"select": {"branches": {
                "a": [{"send": {"to": "handler", "label": "go_a"}}],
                "b": [{"send": {"to": "handler", "label": "go_b"}}],
                "c": [{"send": {"to": "handler", "label": "go_c"}}]}}}]},
            INFORMED)
        assert fail is not None and "router" in fail

    def test_receiver_may_offer_extra_branches(self):
        assert conformance_failure(
            {"handler": [{"branch": {"from": "router", "branches": {
                "go_a": [{"act": {"cap": "fix_a"}}],
                "go_b": [{"act": {"cap": "fix_b"}}],
                "go_c": [{"act": {"cap": "fix_a"}}]}}}]},
            INFORMED) is None

    def test_receiver_dropping_a_branch_is_rejected(self):
        fail = conformance_failure(
            {"handler": [{"branch": {"from": "router", "branches": {
                "go_a": [{"act": {"cap": "fix_a"}}]}}}]},
            INFORMED)
        assert fail is not None and "handler" in fail

    def test_selector_with_wrong_continuation_is_rejected(self):
        fail = conformance_failure(
            {"router": [{"select": {"branches": {
                "a": [{"send": {"to": "handler", "label": "go_a"}}],
                "b": [{"send": {"to": "handler", "label": "wrong"}}]}}}]},
            INFORMED)
        assert fail is not None and "router" in fail

    def test_non_projectable_role_is_reported(self):
        g = [{"choice": {"by": "worker", "branches": {
            "ask": [act("answer", "planner"), act("deliver", "worker")],
            "direct": [act("deliver_direct", "worker")]}}}]
        fail = conformance_failure({"planner": []}, g)
        assert fail is not None and "cannot project" in fail

    def test_generic_subtype_still_permits_fewer_selections(self):
        """The Gay-Hole utility is unchanged; only the checker adapter is
        tightened to the direct rule."""
        contract = ("select", (("a", END), ("b", END)))
        skill = ("select", (("a", END),))
        assert subtype(skill, contract)
        assert conformance_failure(
            {"router": [{"select": {"branches": {
                "a": [{"send": {"to": "handler", "label": "go_a"}}]}}}]},
            INFORMED) is not None


class TestParticipants:
    """`prt(G)`: the paper's participant function, transcribed onto the
    pack's step-list encoding of global types."""

    def test_prt_of_communication_and_action(self):
        g = [{"msg": {"from": "p", "to": "q", "label": "l"}},
             {"act": {"cap": "c", "by": "r"}}]
        assert participants(g) == {"p", "q", "r"}

    def test_goal_marker_involves_nobody(self):
        assert participants([{"goal": "done"}]) == frozenset()
        assert participants([]) == frozenset()

    def test_prt_descends_into_branches_and_loops(self):
        g = [{"choice": {"by": "router", "branches": {
            "a": [{"act": {"cap": "c", "by": "handler"}}],
            "b": [{"rec": {"name": "X", "body": [
                {"act": {"cap": "d", "by": "escalator"}}]}}]}}}]
        assert participants(g) == {"router", "handler", "escalator"}

    def test_spawned_role_is_a_participant(self):
        assert participants([{"spawn": {"role": "worker"}}]) == {"worker"}


class TestParticipantAgreement:
    """The `prt(G) = prt(M)` side condition of T-Comm/T-Act/T-Goal: a pack
    that declares only some roles leaves the rest *assumed* to follow their
    projected contract, and the checker must say so rather than imply it
    decided the whole session."""

    G = [{"choice": {"by": "router", "branches": {
        "simple": [{"msg": {"from": "router", "to": "handler",
                            "label": "go_simple"}},
                   {"act": {"cap": "resolve", "by": "handler"}}]}}}]

    def test_undeclared_participants_are_reported_not_refuted(self):
        rep = conformance_report({"handler": [
            {"branch": {"from": "router", "branches": {
                "go_simple": [{"act": {"cap": "resolve"}}]}}}]}, self.G)
        assert rep.ok
        assert rep.assumed == ("router",)

    def test_fully_declared_session_assumes_nothing(self):
        rep = conformance_report({
            "router": [{"select": {"branches": {
                "simple": [{"send": {"to": "handler", "label": "go_simple"}}]}}}],
            "handler": [{"branch": {"from": "router", "branches": {
                "go_simple": [{"act": {"cap": "resolve"}}]}}}],
        }, self.G)
        assert rep.ok and rep.assumed == ()

    def test_declaring_a_non_participant_with_behaviour_is_refuted(self):
        # 'auditor' is not in prt(G), so its contract is `end`; a non-trivial
        # declared behaviour cannot conform to it.
        rep = conformance_report(
            {"auditor": [{"act": {"cap": "resolve"}}]}, self.G)
        assert not rep.ok
        assert "auditor" in rep.failure

    def test_a_pack_with_no_declared_skills_assumes_every_participant(self):
        rep = conformance_report({}, self.G)
        assert rep.ok
        assert rep.assumed == ("handler", "router")


class TestVerdictCarriesTheAssumption:
    def test_verdict_reports_assumed_participants(self):
        from skillc.checker import check
        v = check({
            "name": "partial", "roles": ["router", "handler"],
            "capabilities": {"resolve": {"owner": "handler",
                                         "add": ["resolved"]}},
            "protocol": TestParticipantAgreement.G,
            "goal": "resolved", "init_true": [],
            "skills": {"handler": [
                {"branch": {"from": "router", "branches": {
                    "go_simple": [{"act": {"cap": "resolve"}}]}}}]},
        })
        assert v.achievable
        assert v.assumed_conformant == ("router",)
        assert v.to_dict()["assumed_conformant"] == ["router"]
