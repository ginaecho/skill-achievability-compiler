import json
from collections import Counter

from scripts.benchmark_compaction import PROFILES, ROOT, assess, make_contract, score
from scripts.benchmark_semantics import audit_goal_reachability
from skillc import check


def test_all_expanded_scenarios_have_independent_labels_and_no_false_certificates():
    cases = json.loads((ROOT / "benchmark" / "compaction_cases.json").read_text())
    counts = Counter()
    for case in cases:
        for profile in PROFILES:
            contract = make_contract(case, profile)
            pack = {"name": case["id"], "protocol": [], **contract}
            oracle = audit_goal_reachability(pack)
            expected = ("ACHIEVABLE" if profile in {"complete", "missing_optional"}
                        else "IMPOSSIBLE")
            assert oracle["truth"] == expected, (case["id"], profile)
            result = check(pack, scope="goal")
            if expected == "ACHIEVABLE":
                assert not result.refuted
            else:
                assert result.context_refuted
            counts[expected] += 1
    assert counts == {"ACHIEVABLE": 16, "IMPOSSIBLE": 16}


def test_benchmark_does_not_hide_abstentions_or_undefined_fpr():
    rows = [
        {"id": "positive", "category": "x", "truth": "IMPOSSIBLE",
         "predicted": "IMPOSSIBLE", "reason": "GOAL_UNSAT"},
        {"id": "abstained", "category": "x", "truth": "ACHIEVABLE",
         "predicted": "UNKNOWN", "reason": "PROTOCOL_ONLY"},
    ]
    metrics = score(rows)
    assert metrics["precision"] == 1
    assert metrics["labelled_coverage"] == 0.5
    assert metrics["false_positive_rate"] is None
    assert metrics["false_positive_rate_all_labelled_achievable"] == 0


def test_assessment_preserves_unbound_failure_and_goal_scope_abstention():
    pack = {"name": "p", "capabilities": {},
            "protocol": [{"act": {"by": "agent", "cap": "optional"}}],
            "goal": "done"}
    contract = {"goal": "done", "capabilities": {"finish": {"add": ["done"]}}}
    rows = assess(pack, contract, {"id": "p"}, "deterministic", "tool_usage_only")
    assert [r["predicted"] for r in rows] == ["IMPOSSIBLE", "IMPOSSIBLE", "UNKNOWN"]
