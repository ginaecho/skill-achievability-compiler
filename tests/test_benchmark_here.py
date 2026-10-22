"""Sandboxed checks for the local-artifact benchmark; no live model is used."""
import importlib.util
import json
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parents[1] / "scripts" / "benchmark_here.py"
SPEC = importlib.util.spec_from_file_location("benchmark_here", PATH)
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


def test_cases_have_no_expected_labels_and_balanced_workflow_shapes():
    assert len(bench.CASES) >= 5
    assert len({c["id"] for c in bench.CASES}) == len(bench.CASES)
    for case in bench.CASES:
        assert "expected" not in case and "feasible" not in case
        assert case["source"]
        assert set(case["ops"]) <= bench.OPS.keys()
        assert set(case["goals"]) <= {p for name in case["ops"] for p in bench.OPS[name]["adds"]}


def test_real_local_git_report_and_archive_are_verified(tmp_path):
    case = next(c for c in bench.CASES if c["id"] == "release-archive")
    truth = bench.oracle(case, tmp_path / "oracle")
    assert truth["feasible"] and all(t["ok"] for t in truth["trace"])
    assert bench.verify("archive", tmp_path / "oracle")
    (tmp_path / "oracle" / "report.md").write_text("corrupted", encoding="utf-8")
    assert not bench.verify("archive", tmp_path / "oracle")


def test_permission_denial_is_explicit_and_no_outside_write_happens(tmp_path):
    result = bench.execute("outside_write", tmp_path)
    assert not result["ok"] and "PermissionError" in result["error"]
    assert list(tmp_path.iterdir()) == []


def test_unmet_dependency_never_runs_executor(tmp_path, monkeypatch):
    monkeypatch.setattr(bench, "execute", lambda *_: pytest.fail("must not execute"))
    result = bench.attempt("report", tmp_path, set())
    assert not result["ok"] and "history_ready" in result["error"]


def test_unknown_operation_is_not_a_command(tmp_path):
    with pytest.raises(ValueError, match="unknown operation"):
        bench.execute("echo unexpected", tmp_path)


@pytest.fixture
def environment(tmp_path, monkeypatch):
    def isolated_probe(**kwargs):
        return bench.probe_original(
            **{**kwargs, "root": tmp_path, "settings": (), "mcp_configs": ()})

    monkeypatch.setattr(bench, "probe_original", bench.probe, raising=False)
    monkeypatch.setattr(bench, "probe", isolated_probe)
    return bench.discover(tmp_path)


def test_discovery_does_not_invent_host_session_tools(environment):
    env, observed = environment
    assert "git" in observed["programs"]
    assert "openpyxl" in observed["modules"]
    assert env.of_kind("tool") == []
    assert observed["permissions"]["outside_write"] is False
    assert "not performed" in observed["mcp"]["live_tools_list"]


def test_preflight_keeps_feasible_branches_when_one_is_missing(environment, tmp_path):
    env, _ = environment
    env.nodes["program/pandoc"]["attrs"]["available"] = False
    env.nodes["program/git"]["attrs"]["available"] = True
    env.nodes["pymodule/rdflib"]["attrs"]["available"] = True
    case = next(c for c in bench.CASES if c["id"] == "combined-handoff")
    row = bench.skillc_trial(case, env, tmp_path / "trial")
    assert row["prediction"] == "IMPOSSIBLE"
    assert row["trace"] == [] and row["model_calls"] == 0
    assert row["goal_predictions"] == {
        "archive_ready": "achievable", "document_ready": "blocked", "graph_ready": "achievable"}
    result = json.loads((tmp_path / "trial" / "preflight.json").read_text(encoding="utf-8"))
    assert result["certificates"]["document_ready"]["reason"] == "GOAL_UNSAT"
    assert {s["op"] for s in result["plan"]} >= {"history", "report", "archive", "graph"}


def test_unprobed_program_abstains_instead_of_false_stop(environment, tmp_path):
    env, _ = environment
    del env.nodes["program/git"]
    case = next(c for c in bench.CASES if c["id"] == "release-report")
    row = bench.skillc_trial(case, env, tmp_path / "trial")
    assert row["prediction"] == "UNKNOWN" and row["trace"] == []


def test_oracle_runs_after_missing_module_and_does_not_use_probe(tmp_path, monkeypatch):
    original = bench.importlib.import_module

    def missing(name):
        if name == "openpyxl":
            raise ModuleNotFoundError("controlled missing openpyxl")
        return original(name)

    monkeypatch.setattr(bench.importlib, "import_module", missing)
    case = next(c for c in bench.CASES if c["id"] == "excel-history")
    truth = bench.oracle(case, tmp_path / "oracle")
    assert not truth["feasible"]
    assert truth["trace"][0]["ok"] and not truth["trace"][1]["ok"]
    assert "ModuleNotFoundError" in truth["trace"][1]["error"]


def _agent(tmp_path, monkeypatch, replies, usage=True, arm="plain"):
    texts = iter(replies)

    def complete(*args, **kwargs):
        if usage:
            bench.providers._record_usage({"input_tokens": 10, "output_tokens": 2,
                                           "cache_read_input_tokens": 3})
        return json.dumps(next(texts))

    monkeypatch.setattr(bench.providers, "complete", complete)
    return bench.agent_trial(
        bench.CASES[0], arm, {"programs": {"git": True}}, tmp_path / "agent",
        provider="azure-openai", model="stub", max_steps=5, timeout=1)


def test_agent_executes_real_actions_and_records_measured_usage(tmp_path, monkeypatch):
    row = _agent(tmp_path, monkeypatch, [
        {"action": "inspect_environment"}, {"action": "history"}, {"action": "report"},
        {"action": "finish", "verdict": "ACHIEVABLE"}])
    assert row["goal_achieved"] and row["error"] is None
    assert row["input_tokens"] == 52 and row["output_tokens"] == 8
    assert row["model_calls"] == 4 and row["discovery_calls"] == 1


def test_model_success_claim_does_not_establish_runtime_success(tmp_path, monkeypatch):
    row = _agent(tmp_path, monkeypatch, [{"action": "finish", "verdict": "ACHIEVABLE"}])
    assert row["prediction"] == "ACHIEVABLE" and not row["goal_achieved"]


def test_agent_cannot_execute_unlisted_action(tmp_path, monkeypatch):
    row = _agent(tmp_path, monkeypatch, [{"action": "outside_write"}])
    assert row["prediction"] == "UNKNOWN"
    assert "allowlist" in row["error"] and not row["trace"]


def test_missing_usage_is_not_presented_as_measured_zero(tmp_path, monkeypatch):
    row = _agent(tmp_path, monkeypatch, [{"action": "finish", "verdict": "UNKNOWN"}], usage=False)
    assert row["usage_complete"] is False


def test_guidance_is_only_difference_in_model_inputs(tmp_path, monkeypatch):
    captured = []

    def complete(provider, system, user, *args):
        captured.append((system, json.loads(user)))
        return '{"action":"finish","verdict":"UNKNOWN"}'

    monkeypatch.setattr(bench.providers, "complete", complete)
    for arm in ("plain", "guided"):
        bench.agent_trial(bench.CASES[0], arm, {}, tmp_path / arm,
                          provider="azure-openai", model="stub", max_steps=1, timeout=1)
    assert captured[0][1] == captured[1][1]
    assert captured[1][0] == captured[0][0] + "\n\n" + bench.GUIDANCE
    assert "programs" not in captured[0][1]["request"]


def test_false_stop_is_detected_independently(tmp_path, monkeypatch):
    row = _agent(tmp_path, monkeypatch, [{"action": "finish", "verdict": "IMPOSSIBLE"}])
    scored = bench.score(row, {"feasible": True})
    assert scored["false_stop"] and not scored["classification_correct"]
    assert not scored["early_correct_stop"]


def test_cli_refuses_overwriting_and_outside_output(tmp_path):
    with pytest.raises(SystemExit):
        bench.main(["--output", str(tmp_path), "--repeats", "1"])


def test_summary_exposes_abstentions_and_failed_calls(tmp_path, monkeypatch):
    row = _agent(tmp_path, monkeypatch, [{"action": "invalid"}])
    result = bench.summarize([bench.score(row, {"feasible": False})])["plain"]
    assert result["unknown"] == 1 and result["errors"] == 1
    assert result["accuracy"] == 0 and result["early_correct_stops"] == 0


def test_partial_report_does_not_require_future_oracles():
    text = bench.report({"created_at": "now", "model": "stub", "repeats": 1,
                         "summary": {}, "cases": bench.CASES, "oracle": {}})
    assert text.count("| pending |") == len(bench.CASES)


def test_report_defines_metrics_and_shows_token_totals(tmp_path, monkeypatch):
    row = _agent(tmp_path, monkeypatch, [{"action": "finish", "verdict": "IMPOSSIBLE"}])
    text = bench.report({
        "created_at": "now", "model": "stub", "repeats": 1,
        "summary": bench.summarize([bench.score(row, {"feasible": False})]),
        "cases": [bench.CASES[0]],
        "oracle": {bench.CASES[0]["id"]: {"feasible": False, "trace": [],
                                          "goal_status": {"report_ready": False}}}})
    assert "| plain | 1/1 | 0 | 1/1 | 0/0 | 15 |" in text
    assert "UNKNOWN is not a definite answer" in text
    assert "Read-only environment inspection is allowed" in text
    assert "across all trials" in text
    assert "report: blocked" in text
    assert "before any task operation" in text
