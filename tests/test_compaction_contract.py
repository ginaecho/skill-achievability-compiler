import pytest
import random

from skillc import check
from skillc.frontend.contract import bind_contract
from skillc.pack import PackError


def test_contract_preserves_declared_goal_and_all_available_alternatives():
    extracted = {
        "name": "weak", "capabilities": {"invented": {"add": ["done"]}},
        "protocol": [{"act": {"cap": "invented", "by": "agent"}}],
        "goal": True,
    }
    contract = {
        "goal": "published",
        "capabilities": {"alternate": {"owner": "agent", "add": ["published"]}},
    }
    bound = bind_contract(extracted, contract)
    assert bound["goal"] == "published"
    assert bound["capabilities"] == contract["capabilities"]
    assert bound["protocol"] == extracted["protocol"]
    assert extracted["goal"] is True
    assert check(bound, scope="goal").unknown


def test_contract_does_not_let_compactor_grant_a_missing_essential_tool():
    extracted = {
        "name": "invented", "capabilities": {"publish": {"add": ["done"]}},
        "protocol": [{"act": {"cap": "publish", "by": "agent"}}], "goal": "done",
    }
    bound = bind_contract(extracted, {"goal": "done", "capabilities": {}})
    assert check(bound, scope="goal").refuted


def test_contract_rebinds_goal_markers_without_moving_them():
    extracted = {"name": "marker", "capabilities": {},
                 "protocol": [{"choice": {"by": "agent", "branches": {
                     "a": [{"goal": True}], "b": [{"goal": True}]}}}],
                 "goal": True}
    bound = bind_contract(extracted, {"goal": "done", "capabilities": {}})
    branches = bound["protocol"][0]["choice"]["branches"]
    assert branches["a"] == [{"goal": "done"}]
    assert branches["b"] == [{"goal": "done"}]


def test_contract_rejects_unknown_fields_and_missing_goal():
    extracted = {"name": "p", "capabilities": {}, "protocol": [], "goal": True}
    with pytest.raises(PackError):
        bind_contract(extracted, {"capabilities": {}})
    with pytest.raises(PackError):
        bind_contract(extracted, {"goal": True, "capabilities": {}, "typo": True})


def test_context_certificates_agree_with_exhaustive_boolean_oracle():
    from scripts.benchmark_semantics import audit_goal_reachability

    rng = random.Random(21)
    atoms = ["a", "b", "c"]
    for index in range(80):
        caps = {}
        for action in range(3):
            predicate = rng.choice(atoms)
            caps[f"step_{action}"] = {
                "pre": rng.choice([True, predicate, {"not": predicate}]),
                "add": [rng.choice(atoms)],
                "del": rng.sample(atoms, rng.randrange(2)),
            }
        pack = {
            "name": f"finite-{index}", "capabilities": caps,
            "protocol": [{"act": {"cap": name, "by": "agent"}} for name in caps],
            "init_true": rng.sample(atoms, rng.randrange(4)),
            "goal": {"and": rng.sample(atoms, rng.randrange(1, 4))},
        }
        result = check(pack, scope="goal")
        oracle = audit_goal_reachability(pack)
        assert oracle["truth"] != "UNKNOWN"
        if result.refuted:
            assert oracle["truth"] == "IMPOSSIBLE", pack
