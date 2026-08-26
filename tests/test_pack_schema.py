import pytest

from skillc.evaluate import load_corpus
from skillc.pack import Pack, PackError, pack_digest, validate_pack

MINIMAL = {
    "name": "m",
    "capabilities": {"a": {"add": ["done"]}},
    "protocol": [{"act": {"cap": "a", "by": "agent"}}],
    "goal": "done",
}


def test_minimal_pack_passes_gate():
    validate_pack(MINIMAL)
    p = Pack.load(MINIMAL)
    assert p.capabilities["a"].add == ["done"]


@pytest.mark.parametrize("mutate,exc_fragment", [
    (lambda d: d.pop("goal"), "missing top-level key"),
    (lambda d: d.pop("capabilities"), "missing top-level key"),
    (lambda d: d.update(protocol=[{"act": {"cap": "a"}}]), "act needs cap+by"),
    (lambda d: d.update(protocol=[{"jump": {}}]), "unknown step kind"),
    (lambda d: d.update(protocol=[{"msg": {"from": "a", "to": "b"}}]), "msg needs"),
    (lambda d: d.update(goal={"cmp": ["x", "~", 1]}), "bad cmp"),
    (lambda d: d.update(capabilities={"a": {"pre": {"nand": []}}}), "bad formula"),
    (lambda d: d.update(protocol=[{"choice": {"by": "r", "branches": {}}}]),
     "at least one branch"),
    (lambda d: d.update(init_true="oops"), "init_true"),
])
def test_gate_rejects(mutate, exc_fragment):
    d = {k: (dict(v) if isinstance(v, dict) else list(v) if isinstance(v, list) else v)
         for k, v in MINIMAL.items()}
    mutate(d)
    import re
    with pytest.raises(PackError, match=re.escape(exc_fragment)):
        validate_pack(d)


def test_undeclared_cap_passes_gate():
    # The gate deliberately lets undeclared caps through: the CHECKER reports
    # them as MISSING_CAPABILITY (that is the hallucinated-planning signal).
    d = dict(MINIMAL, protocol=[{"act": {"cap": "ghost_tool", "by": "agent"}}])
    validate_pack(d)


def test_all_reference_compactions_are_well_formed():
    corpus = load_corpus()
    assert len(corpus) == 15
    for c in corpus:
        validate_pack(c["pack"])


# --------------------------------------------------------------------------
# QF-LIA: multiplication needs an integer-constant operand
# --------------------------------------------------------------------------

@pytest.mark.parametrize("expr", [
    {"*": ["x", "y"]},
    {"*": [{"+": ["x", 1]}, "y"]},
    {"*": [{"*": [2, "x"]}, "y"]},
])
def test_gate_rejects_variable_times_variable(expr):
    d = dict(MINIMAL, capabilities={"a": {"assigns": {"z": expr}}})
    with pytest.raises(PackError, match="QF-LIA"):
        validate_pack(d)


@pytest.mark.parametrize("expr", [
    {"*": [2, "x"]},
    {"*": ["x", 2]},
    {"*": [{"+": [2, 3]}, "x"]},
    {"*": [{"-": ["x", 1]}, 4]},
])
def test_gate_accepts_linear_multiplication(expr):
    validate_pack(dict(MINIMAL, capabilities={"a": {"assigns": {"z": expr}}}))


def test_gate_rejects_nonlinear_goal_comparison():
    d = dict(MINIMAL, goal={"cmp": [{"*": ["x", "y"]}, ">", 0]})
    with pytest.raises(PackError, match="QF-LIA"):
        validate_pack(d)


# --------------------------------------------------------------------------
# Typed conversion + pack identity
# --------------------------------------------------------------------------

def test_pack_to_dict_round_trips_through_the_gate():
    p = Pack.load(MINIMAL)
    d = p.to_dict()
    validate_pack(d)
    assert Pack.load(d).to_dict() == d
    assert d["capabilities"]["a"]["add"] == ["done"]
    assert d["capabilities"]["a"]["del"] == []


def test_pack_to_dict_rejects_untyped_capabilities():
    p = Pack(name="m", roles=[], capabilities={"a": {"add": ["done"]}},
             protocol=[], goal="done")
    with pytest.raises(PackError, match="Capability"):
        p.to_dict()


def test_pack_digest_is_stable_and_normalising():
    verbose = dict(MINIMAL, roles=[], init_true=[], init_constraints=[],
                   skills={}, capabilities={"a": {"owner": "?", "pre": True,
                                                  "add": ["done"], "del": []}})
    assert pack_digest(MINIMAL) == pack_digest(verbose)
    assert pack_digest(MINIMAL) == pack_digest(Pack.load(MINIMAL))
    assert pack_digest(MINIMAL) != pack_digest(dict(MINIMAL, goal="other"))
    assert pack_digest(MINIMAL).startswith("sha256:")


def test_pack_digest_validates_its_input():
    with pytest.raises(PackError):
        pack_digest({"name": "x"})
