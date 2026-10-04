from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest
from scripts.benchmark_semantics import World, audit_goal_reachability, holds


SCRIPT = (
    Path(__file__).parents[1] / "scripts" / "benchmark_real_rejections.py"
)
SPEC = importlib.util.spec_from_file_location("real_rejection_benchmark", SCRIPT)
assert SPEC and SPEC.loader
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


def run_trial(monkeypatch, tmp_path, pack, capability):
    source = tmp_path / "SKILL.md"
    source.write_text("Complete the declared goal.", encoding="utf-8")
    replies = iter([
        {"status": "attempt", "capability": capability},
        {"status": "blocked", "reason": "No further action"},
    ])
    calls = []

    def fake_call(**kwargs):
        calls.append(json.loads(json.dumps(kwargs["messages"])))
        return {
            "output_text": json.dumps(next(replies)),
            "usage": {"input": 1, "output": 1, "total": 2},
            "latency_ms": 1,
        }

    monkeypatch.setattr(benchmark, "call_json", fake_call)
    result = benchmark.run_ungated_trial(
        case={"id": "regression", "source_path": str(source)},
        pack=pack, restricted_capability="unavailable",
        endpoint="https://example.openai.azure.com/openai/v1",
        credential="unused-test-credential", use_api_key=True,
        model="test", trial=1, max_turns=2,
        ledger_path=tmp_path / "calls.jsonl")
    return result, calls


def test_runtime_rejects_action_with_false_precondition(monkeypatch, tmp_path):
    result, calls = run_trial(monkeypatch, tmp_path, {
        "capabilities": {"publish": {"pre": "approved", "add": ["done"]}},
        "goal": "done",
    }, "publish")
    assert result["outcome"] == "blocked"
    feedback = json.loads(calls[1][-1]["content"])
    assert feedback["success"] is False
    assert feedback["error"] == "precondition_unsatisfied"
    assert "done" not in feedback["true_predicates"]


def test_runtime_applies_numeric_effect_and_goal(monkeypatch, tmp_path):
    result, _ = run_trial(monkeypatch, tmp_path, {
        "capabilities": {"set": {"assigns": {"x": 3}}},
        "goal": {"cmp": ["x", "==", 3]},
    }, "set")
    assert result["outcome"] == "achieved"
    assert result["turns"] == 1


def test_runtime_delete_wins_over_overlapping_add(monkeypatch, tmp_path):
    result, _ = run_trial(monkeypatch, tmp_path, {
        "capabilities": {"clear": {"add": ["done"], "del": ["done"]}},
        "goal": {"not": "done"},
    }, "clear")
    assert result["outcome"] == "achieved"


def test_numeric_updates_use_old_world_and_assignments_take_precedence():
    world = World(set(), {"x": 0, "y": 1})
    successor, error = world.transition({
        "nondet": {"x": {"cmp": ["x", "==", "y"]},
                   "y": {"cmp": ["y", "==", "x"]}}})
    assert error is None
    assert successor.values == {"x": 1, "y": 0}
    successor, error = world.transition({
        "assigns": {"x": 4}, "nondet": {"x": False}})
    assert error is None
    assert successor.values["x"] == 4


def test_numeric_guard_and_empty_effect_do_not_change_world():
    world = World({"ready"}, {"x": 0})
    assert world.transition({"pre": {"cmp": ["x", ">", 0]}}) == (
        None, "precondition_unsatisfied")
    assert world.transition({"nondet": {"x": False}}) == (
        None, "effect_unsatisfiable")
    assert world.values == {"x": 0}
    assert world.predicates == {"ready"}


def test_unsupported_formula_and_unbound_numbers_are_not_silent_failures():
    with pytest.raises(ValueError, match="unsupported formula"):
        benchmark.goal_satisfied({"unknown_operator": True}, set())
    with pytest.raises(KeyError):
        benchmark.goal_satisfied({"cmp": ["x", "==", 0]}, set())


def test_independent_oracle_proves_missing_establisher_and_accepts_alternative():
    pack = {"capabilities": {"alternate": {"add": ["done"]}},
            "protocol": [{"act": {"cap": "missing", "by": "agent"}}],
            "goal": "done"}
    audit = audit_goal_reachability(pack)
    assert audit["truth"] == "ACHIEVABLE"
    assert audit["witness"][0]["capability"] == "alternate"
    assert audit_goal_reachability({**pack, "goal": "never"})["truth"] == "IMPOSSIBLE"


def test_numeric_oracle_failure_abstains_instead_of_proving_impossibility():
    audit = audit_goal_reachability({
        "capabilities": {}, "goal": {"cmp": ["x", "==", 1]}})
    assert audit["truth"] == "UNKNOWN"


def test_initial_numeric_world_satisfies_declared_constraints():
    pack = {"capabilities": {}, "init_constraints": [
        {"cmp": ["x", "==", 7]}], "goal": {"cmp": ["x", "==", 7]}}
    world = World.initial(pack)
    assert world.values == {"x": 7}
    assert holds(pack["goal"], world.predicates, world.values)


def test_reuse_compaction_checks_source_and_model_output(tmp_path):
    case = {"id": "sample", "source_sha256": "source",
            "license_sha256": "license", "source_commit": "revision"}
    pack = {"name": "sample", "capabilities": {}, "protocol": [], "goal": True}
    (tmp_path / "packs").mkdir()
    (tmp_path / "packs" / "sample.json").write_text(json.dumps(pack))
    (tmp_path / "manifest.json").write_text(json.dumps({"cases": [case]}))
    row = {"phase": "compaction", "case_id": "sample",
           "output_text": json.dumps(pack), "usage": {"total": 10}}
    (tmp_path / "calls.jsonl").write_text(json.dumps(row) + "\n")
    reused, rows = benchmark.reuse_compaction(case, tmp_path)
    assert reused == pack
    assert rows == [row]
    with pytest.raises(ValueError, match="provenance"):
        benchmark.reuse_compaction({**case, "source_sha256": "changed"}, tmp_path)
    (tmp_path / "packs" / "sample.json").write_text(
        json.dumps({**pack, "goal": False}))
    with pytest.raises(ValueError, match="differs"):
        benchmark.reuse_compaction(case, tmp_path)


def test_validate_endpoint_accepts_only_azure_openai_inference_endpoint():
    assert benchmark.validate_endpoint(
        "https://example.openai.azure.com/openai/v1/"
    ) == "https://example.openai.azure.com/openai/v1"
    with pytest.raises(ValueError):
        benchmark.validate_endpoint(
            "https://example.services.ai.azure.com/api/projects/demo"
        )
    with pytest.raises(ValueError):
        benchmark.validate_endpoint("https://attacker.example/openai/v1")


def test_restrict_pack_produces_missing_capability_verdict():
    pack = {
        "name": "write-result",
        "roles": ["agent"],
        "capabilities": {
            "prepare": {"owner": "agent", "add": ["prepared"]},
            "write": {
                "owner": "agent",
                "pre": "prepared",
                "add": ["written"],
            },
        },
        "protocol": [
            {"act": {"cap": "prepare", "by": "agent"}},
            {"act": {"cap": "write", "by": "agent"}},
        ],
        "goal": "written",
    }
    restricted = benchmark.restrict_pack(pack, "write")
    verdict = benchmark.check(restricted)
    assert verdict.reason == "MISSING_CAPABILITY"
    assert verdict.frontier == ("write",)


def test_select_restricted_capability_falls_back_to_goal_establisher():
    pack = {
        "capabilities": {
            "prepare": {"add": ["prepared"]},
            "finish": {"add": ["done"]},
        },
        "goal": {"and": ["prepared", "done"]},
    }
    assert benchmark.select_restricted_capability(pack, "renamed") == "finish"


def test_goal_satisfied_handles_boolean_formulas():
    goal = {"and": ["built", {"or": ["tested", "reviewed"]}]}
    assert benchmark.goal_satisfied(goal, {"built", "tested"})
    assert not benchmark.goal_satisfied(goal, {"built"})


def test_aggregate_keeps_one_time_gate_cost_separate_from_runtime_mean():
    results = [
        {
            "with_skillc": {
                "usage": {"total": 100},
                "total_latency_ms": 1000,
            },
            "without_skillc": {
                "mean_tokens": 40,
                "mean_latency_ms": 300,
            },
        },
        {
            "with_skillc": {
                "usage": {"total": 200},
                "total_latency_ms": 2000,
            },
            "without_skillc": {
                "mean_tokens": 60,
                "mean_latency_ms": 700,
            },
        },
    ]
    summary = benchmark.aggregate(results)
    assert summary["compaction_tokens_once_per_source_version"] == 300
    assert summary["mean_ungated_tokens_per_one_invocation_across_cases"] == 100
    assert summary["net_tokens_saved_at_one_invocation"] == -200
    assert summary["token_break_even_invocations"] == 3
