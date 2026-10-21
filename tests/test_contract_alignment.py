"""Alignment through bindings (PLAN Addendum E-e): a pack's own state names are
renamed to the environment's contract atoms when the binding makes it unambiguous."""
from skillc import check
from skillc.frontend.contracts import align_to_contracts, apply_contracts, bind_environment

STATES = {"doc_drafted": "", "doc_published": "", "approved": ""}
CONTRACTS = {"draft": {"pre": True, "add": ["doc_drafted"]},
             "publish": {"pre": "doc_drafted", "add": ["doc_published"]}}


def _pack(capabilities, goal, protocol, init_true=()):
    return {"name": "t", "roles": ["agent"], "capabilities": capabilities,
            "protocol": [{"act": {"cap": c, "by": "agent"}} for c in protocol],
            "goal": goal, "init_true": list(init_true)}


def _blind_pack(**extra):
    return _pack({"draft": {"owner": "agent", "add": ["draft_written"]},
                  "publish": {"owner": "agent", "pre": "draft_written",
                              "add": ["report_live"]}},
                 {"and": ["draft_written", "report_live"]}, ["draft", "publish"], **extra)


def test_unique_single_atom_bindings_are_renamed_everywhere():
    pack = _blind_pack(init_true=["user_logged_in"])
    pack["protocol"].append({"goal": {"and": ["draft_written", "report_live"]}})

    a = align_to_contracts(pack, CONTRACTS, STATES)

    assert dict(a.renamed) == {"draft_written": "doc_drafted", "report_live": "doc_published"}
    assert a.pack["goal"] == {"and": ["doc_drafted", "doc_published"]}
    assert a.pack["capabilities"]["publish"]["pre"] == "doc_drafted"
    assert a.pack["capabilities"]["publish"]["add"] == ["doc_published"]
    assert a.pack["protocol"][-1] == {"goal": {"and": ["doc_drafted", "doc_published"]}}
    assert a.pack["init_true"] == [] and a.dropped_init == ("user_logged_in",)
    assert pack["goal"] == {"and": ["draft_written", "report_live"]}     # input untouched


def test_alignment_is_opt_in_and_lets_contracts_apply():
    pack = _blind_pack()
    off = apply_contracts(pack, CONTRACTS, STATES)
    assert off.unaligned == ("draft_written", "report_live") and off.applied == ()

    on = apply_contracts(pack, CONTRACTS, STATES, align=True)
    assert on.unaligned == () and on.applied == ("draft", "publish")
    assert dict(on.renamed) == {"draft_written": "doc_drafted", "report_live": "doc_published"}
    assert check(on.pack).label == "ACHIEVABLE"

    env = {"contracts": CONTRACTS, "states": STATES, "init_true": []}
    assert bind_environment(pack, ["draft", "publish"], env).unaligned
    assert not bind_environment(pack, ["draft", "publish"], env, align=True).unaligned


def test_aligned_pack_still_refuted_by_a_defective_contract():
    contracts = {**CONTRACTS, "publish": {"pre": {"and": ["doc_drafted", "approved"]},
                                          "add": ["doc_published"]}}
    aligned = align_to_contracts(_blind_pack(), CONTRACTS, STATES).pack
    assert check(apply_contracts(aligned, contracts, STATES).pack).reason == "BLOCKED_GUARD"


def test_two_pack_tools_adding_the_same_atom_are_not_renamed():
    pack = _pack({"draft": {"owner": "agent", "add": ["draft_written"]},
                  "redraft": {"owner": "agent", "add": ["draft_written"]},
                  "publish": {"owner": "agent", "pre": "draft_written",
                              "add": ["report_live"]}},
                 "report_live", ["draft", "publish"])
    contracts = {**CONTRACTS, "redraft": {"pre": True, "add": ["doc_drafted"]}}

    a = align_to_contracts(pack, contracts, STATES)

    assert dict(a.renamed) == {"report_live": "doc_published"}
    assert a.pack["capabilities"]["publish"]["pre"] == "draft_written"
    assert apply_contracts(pack, contracts, STATES, align=True).unaligned == ()  # goal aligned
    pack["goal"] = {"and": ["draft_written", "report_live"]}
    assert apply_contracts(pack, contracts, STATES, align=True).unaligned == ("draft_written",)


def test_contract_adding_two_atoms_is_not_renamed():
    contracts = {"draft": {"pre": True, "add": ["doc_drafted", "approved"]},
                 "publish": CONTRACTS["publish"]}

    a = align_to_contracts(_blind_pack(), contracts, STATES)

    assert dict(a.renamed) == {"report_live": "doc_published"}
    assert apply_contracts(_blind_pack(), contracts, STATES, align=True).unaligned \
        == ("draft_written",)


def test_vocabulary_names_and_unbound_tools_are_left_alone():
    pack = _pack({"draft": {"owner": "agent", "add": ["approved"]},
                  "notes": {"owner": "agent", "add": ["notes_taken"]}},
                 {"and": ["approved", "notes_taken"]}, ["draft", "notes"])

    a = align_to_contracts(pack, CONTRACTS, STATES)

    assert a.renamed == ()
    assert apply_contracts(pack, CONTRACTS, STATES, align=True).unaligned == ("notes_taken",)
