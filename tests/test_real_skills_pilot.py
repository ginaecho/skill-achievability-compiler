import json
import time
from types import SimpleNamespace

import pytest

from scripts import real_skills_pilot as pilot
from scripts import real_skills_runtime as runtime
from skillc.frontend import providers
from scripts.real_skills_pilot import amend_transport, digest, native_usage, pure_refactor


REFACTORED = b"""
import re
def name_tokens(name):
    return sorted({name} | set(name.split("-")), key=len, reverse=True)
def masked(text, name):
    t = text.lower()
    for tok in name_tokens(name):
        if len(tok) >= 3:
            t = re.sub(r"\\b" + re.escape(tok) + r"\\b", "x", t)
    return t
"""


def test_pure_refactor_rejects_io_and_requires_actual_extraction():
    assert pure_refactor(REFACTORED) is None
    assert pure_refactor(REFACTORED.replace(b"name_tokens(name):", b"unrelated(name):"))
    assert pure_refactor(REFACTORED + b"\nopen('/tmp/result', 'w')\n")
    assert pure_refactor(REFACTORED.replace(b"t = text.lower()", b"import this\n    t = text.lower()"))


def test_native_usage_counts_only_explicit_receipts_without_double_counting_cache(tmp_path):
    usage = {"tokenDetails": {
        "input": {"tokenCount": 3}, "cache_read": {"tokenCount": 5},
        "cache_write": {"tokenCount": 7}, "output": {"tokenCount": 11},
    }, "totalNanoAiu": 13}
    call = tmp_path / "call-1"
    call.mkdir()
    (call / "usage.json").write_text(json.dumps(usage))
    duplicate = call / "home"
    duplicate.mkdir()
    (duplicate / "usage.json").write_text(json.dumps(usage))
    result = native_usage(tmp_path)
    assert result == {
        "disjoint_tokens": {"input": 3, "cache_read": 5, "cache_write": 7, "output": 11},
        "reported_nano_aiu": 13, "usage_files": 1,
    }


@pytest.mark.parametrize("missing", [False, True])
def test_native_usage_rejects_malformed_counters_without_imputing_zero(tmp_path, missing):
    call = tmp_path / "call-1"
    call.mkdir()
    details = {} if missing else {
        key: {"tokenCount": -1} for key in ("input", "cache_read", "cache_write", "output")
    }
    (call / "usage.json").write_text(json.dumps({
        "tokenDetails": details, "totalNanoAiu": 13,
    }))
    with pytest.raises(RuntimeError, match="required counters|invalid counters"):
        native_usage(tmp_path)


def test_transport_amendment_preserves_original_freeze_and_exact_public_inputs(tmp_path):
    old = tmp_path / "pilot"
    case = old / "skill"
    case.mkdir(parents=True)
    (case / "input.py").write_bytes(REFACTORED)
    (case / "LICENSE").write_text("public test fixture")
    original = json.dumps({
        "models": ["model"], "repeats": 5,
        "cases": [{"id": "skill", "input_sha256": digest(REFACTORED)}],
    }).encode()
    (old / "frozen.json").write_bytes(original)
    amend_transport(tmp_path)
    new = tmp_path / "pilot-guarded"
    assert (old / "frozen.json").read_bytes() == original
    assert (new / "skill" / "input.py").read_bytes() == REFACTORED
    frozen = json.loads((new / "frozen.json").read_bytes())
    assert frozen["trial_namespace"] == "pilot-guarded-trials"
    assert "native_adapter" in frozen["implementation_sha256"]
    with pytest.raises(ValueError, match="refusing to replace"):
        amend_transport(tmp_path)


@pytest.fixture
def executor(tmp_path, monkeypatch):
    state = {"results": [{"status": "completed", "exit_code": 0}], "passed": True,
             "read_error": None, "native_error": None, "stopped": False, "verified": False,
             "event_tail": b"", "actual": REFACTORED,
             "case": {"id": pilot.FOWLER, "target": "/work/textmask.py"}, "original": REFACTORED}

    class Workspace:
        container = "a" * 64

        def start(self, *args):
            state["seeded"] = args

        def read(self, path):
            if state["read_error"]:
                raise state["read_error"]
            state["snapshot_target"] = path
            return state["actual"]

        def stop(self):
            state["stopped"] = True

    def complete(*args, **kwargs):
        state["server_config"] = json.loads((tmp_path / "server.json").read_bytes())
        events = [{"type": "server_start", "credential_environment_present": False}]
        for call, result in enumerate(state["results"], 1):
            events.append({"type": "tool_start", "call": call, "code": "pass"})
            if result is not None:
                events.append({"type": "tool_result", "call": call,
                               "timestamp": time.time(), **result})
        (tmp_path / "tools.jsonl").write_bytes(
            "\n".join(map(json.dumps, events)).encode() + state["event_tail"])
        if state["native_error"]:
            raise state["native_error"]
        return "Done", {"usage_native": [{"isByok": False}]}

    def verify(*args, **kwargs):
        state["verified"] = True
        state["verification_options"] = kwargs
        return {"passed": state["passed"], "kind": "independent_behavior_checks"}

    def workspace(host, **options):
        state["sandbox_options"] = options
        return Workspace()

    monkeypatch.setattr(pilot, "Sandbox", workspace)
    monkeypatch.setattr(pilot, "copilot_mcp_session", complete)
    monkeypatch.setattr(pilot, "verify", verify)
    state["run"] = lambda: pilot.execute_task(
        state["case"], "Task.", "model",
        tmp_path, "stub-token", "unused", state["original"], tmp_path / "proof.json")
    return state


def test_symbolic_executor_passes_the_same_immutable_runtime_to_its_tool_server(executor):
    executor["case"] = {"id": pilot.SYMBOLIC, "target": "/work/roots.py",
                        "runtime_profile": "sympy", "writable_inputs": []}
    executor["original"] = {"core-capabilities.md": b"roots(x**2-1, x)\n"}
    assert executor["run"]()["outcome"] == "verified_goal_achieved"
    assert executor["sandbox_options"] == {"image": pilot.SYMBOLIC_IMAGE, "site_packages": True}
    assert executor["server_config"]["image"] == pilot.SYMBOLIC_IMAGE
    assert executor["server_config"]["site_packages"] is True
    assert executor["seeded"] == (executor["original"], [])


@pytest.mark.parametrize(("regular", "read_error"), [
    (False, None), (True, None), (True, runtime.DeliverableUnavailable("PermissionError")),
])
def test_instruction_executor_retains_trusted_state_and_does_not_read_nonregular_paths(
        executor, tmp_path, monkeypatch, regular, read_error):
    executor["case"] = {"id": pilot.INSTRUCTIONS, "target": "/work/AGENTS.md",
                        "runtime_profile": "instruction-files", "writable_inputs": ["CLAUDE.md"]}
    executor["original"] = {"CLAUDE.md": b"Original instructions\n"}
    executor["read_error"] = read_error
    filesystem = {"old_path_lexists": True, "canonical_regular_file": regular}
    monkeypatch.setattr(pilot, "instruction_filesystem_snapshot", lambda sandbox: filesystem)
    executor["passed"] = False
    assert executor["run"]()["outcome"] == "verified_goal_not_achieved_with_runtime_evidence"
    assert json.loads((tmp_path / "filesystem_snapshot.json").read_bytes()) == filesystem
    assert executor["verification_options"] == {"filesystem_snapshot": filesystem}
    assert ("snapshot_target" in executor) is (regular and read_error is None)
    assert (tmp_path / "actual.md").exists() is (regular and read_error is None)
    if read_error is not None:
        assert json.loads((tmp_path / "verification.json").read_bytes())["snapshot_error"] == str(read_error)
    assert executor["stopped"]


@pytest.mark.parametrize("case", [
    {"id": pilot.SYMBOLIC}, {"id": pilot.SYMBOLIC, "runtime_profile": "sqlite"},
    {"id": pilot.FOWLER, "runtime_profile": "sympy"},
])
def test_symbolic_profile_cannot_be_substituted_for_another_task(case):
    with pytest.raises(ValueError, match="runtime profile"):
        pilot.task_runtime(case)


def test_missing_deliverable_is_verified_unmet_not_harness_error(executor, tmp_path):
    executor["read_error"] = runtime.DeliverableUnavailable("FileNotFoundError")
    result = executor["run"]()
    assert result["outcome"] == "verified_goal_not_achieved_with_runtime_evidence"
    assert json.loads((tmp_path / "verification.json").read_text())["kind"] == (
        "unavailable_deliverable")
    assert not (tmp_path / "actual.py").exists()
    assert executor["stopped"]


@pytest.mark.parametrize(("exit_code", "passed"), [(0, False), (1, True)])
def test_tool_errors_do_not_decide_independently_verified_goal(executor, exit_code, passed):
    executor["results"][0]["exit_code"] = exit_code
    executor["passed"] = passed
    result = executor["run"]()
    assert (result["outcome"] == "verified_goal_achieved") == passed
    assert result["tool_errors"] == (exit_code != 0)
    assert executor["verified"] and executor["stopped"]


@pytest.mark.parametrize("status", ["tool_timeout", "output_limit", "budget_exhausted"])
def test_executor_records_exact_tool_limit_without_claiming_goal_failure(executor, status):
    executor["results"] = [{"status": status, "exit_code": None}]
    result = executor["run"]()
    assert result["outcome"] == "budget_exhausted"
    assert result["termination_reason"] == status
    assert result["tool_errors"] == 0
    assert not executor["verified"] and executor["stopped"]


def test_native_deadline_retains_incomplete_tool_call_and_unknown_accounting(executor):
    executor["results"] = [None]
    executor["native_error"] = providers.CopilotSessionTimeout(
        "Native model deadline exceeded", {"usage_native": []})
    executor["event_tail"] = b'\n{"type":"tool_result'
    result = executor["run"]()
    assert result["outcome"] == "budget_exhausted"
    assert result["termination_reason"] == "native_session_deadline"
    assert result["accounting_complete"] is False
    assert result["tool_calls"] == result["incomplete_tool_calls"] == 1
    assert result["tool_events_truncated"] is True
    assert not executor["verified"] and executor["stopped"]


def test_normal_completion_cannot_silently_discard_a_corrupt_tool_event(executor):
    executor["event_tail"] = b'\n{"type":"tool_result'
    with pytest.raises(json.JSONDecodeError):
        executor["run"]()
    assert executor["stopped"]


def test_unexplained_sandbox_stop_and_transport_failure_are_harness_errors(executor):
    executor["results"] = [{"status": "sandbox_stopped", "exit_code": None}]
    with pytest.raises(RuntimeError, match="unexpected"):
        executor["run"]()
    assert executor["stopped"]
    executor["native_error"] = RuntimeError("transport failed")
    with pytest.raises(RuntimeError, match="transport failed"):
        executor["run"]()


@pytest.mark.parametrize("rejected_first_call", [False, True])
def test_compaction_deadline_is_unknown_and_counts_every_attempt(
        tmp_path, monkeypatch, rejected_first_call):
    calls = []

    def complete(*args, **kwargs):
        calls.append(kwargs["directory"])
        if rejected_first_call and len(calls) == 1:
            return "invalid compaction", {"usage_native": [{"isByok": False}]}
        raise providers.CopilotSessionTimeout("deadline", {"usage_native": []})

    monkeypatch.setattr(pilot, "copilot_text_session", complete)
    monkeypatch.setattr(pilot.bcr, "parse_reply", lambda *a: {"ok": False, "error": "syntax"})
    result = pilot.compile_task({"id": "skill"}, "Task.", "model", tmp_path, "stub-token")
    assert result["verdict"] == "UNKNOWN"
    assert result["outcome"] == "budget_exhausted"
    assert result["calls"] == len(calls) == 1 + rejected_first_call
    assert result["completed_calls"] == rejected_first_call
    assert result["accounting_complete"] is False
    assert result["static_validation_model_tokens"] == 0


def test_compaction_deadline_preserves_the_prior_valid_static_refutation(tmp_path, monkeypatch):
    calls = []

    def complete(*args, **kwargs):
        calls.append(kwargs["directory"])
        if len(calls) == 1:
            return "Skill `skill`.\n", {"usage_native": [{"isByok": False}]}
        raise providers.CopilotSessionTimeout("deadline", {"usage_native": []})

    monkeypatch.setattr(pilot, "copilot_text_session", complete)
    monkeypatch.setattr(pilot.bcr, "parse_reply", lambda *a: {
        "ok": True, "pack": None, "parsed": {}, "withdrawn": [], "blocked": [],
    })
    monkeypatch.setattr(pilot, "check", lambda _: SimpleNamespace(label="IMPOSSIBLE"))
    monkeypatch.setattr(pilot.bcr, "explain_refutation", lambda *a: "refutation")
    result = pilot.compile_task({"id": "skill"}, "Task.", "model", tmp_path, "stub-token")
    assert result["verdict"] == "IMPOSSIBLE"
    assert result["calls"] == 2 and result["completed_calls"] == 1
    assert result["accounting_complete"] is False


@pytest.fixture
def trial_run(tmp_path, monkeypatch):
    run, cache = tmp_path / "run", tmp_path / "cache"
    case = {"id": pilot.FOWLER, "input_sha256": digest(REFACTORED),
            "task_request": "Task.", "skill_source": {
                "path_in_repo": "SKILL.md", "sha256": digest(b"public skill text")}}
    folder = run / "pilot-guarded" / case["id"]
    folder.mkdir(parents=True)
    original = folder / "input.py"
    original.write_bytes(REFACTORED)
    (cache / "bundles").mkdir(parents=True)
    (cache / "objects").mkdir()
    (cache / "objects" / "blob").write_bytes(b"public skill text")
    (cache / "bundles" / (case["id"] + ".json")).write_text(json.dumps({
        "files": [{"path": "SKILL.md", "git_blob": "blob"}],
    }))
    frozen = {"scope": "pilot", "models": ["model"], "repeats": 1, "cases": [case],
              "trial_namespace": "controller-test-trials",
              "implementation_sha256": {"fixture": digest(REFACTORED)}}
    (folder.parent / "frozen.json").write_text(json.dumps(frozen))
    monkeypatch.setattr(pilot, "implementation_files", lambda: {"fixture": original})
    monkeypatch.setattr(pilot, "verify_copilot_text_receipt", lambda *a: None)
    monkeypatch.setattr(pilot.subprocess, "check_output", lambda *a, **k: (
        "npipe:////./pipe/stub" if a[0][0] == "docker" else "unused"))
    monkeypatch.setattr(pilot.shutil, "disk_usage", lambda _: SimpleNamespace(free=10**12))
    return run, cache, folder.parent


def test_executor_seeds_json_and_text_inputs_and_retains_json_deliverable(
        executor, tmp_path):
    originals = {"mewt-results.json": b'{"results":[]}', "mewt-status.txt": b"public export"}
    executor["actual"] = b'{"campaign":{}}'
    pilot.execute_task(
        {"id": pilot.MUTATION, "target": "/work/mutation-summary.json", "writable_inputs": []},
        "Inventory public exports.", "model", tmp_path, "stub-token", "unused",
        originals, tmp_path / "proof.json")
    assert executor["seeded"] == (originals, [])
    assert executor["snapshot_target"] == "/work/mutation-summary.json"
    assert (tmp_path / "actual.json").read_bytes() == executor["actual"]
    assert not (tmp_path / "actual.py").exists()
    assert executor["verified"] and executor["stopped"]


def test_controller_refuses_review_only_manifest_before_authentication(trial_run, monkeypatch):
    run, cache, folder = trial_run
    manifest = folder / "frozen.json"
    frozen = json.loads(manifest.read_bytes())
    frozen["execution_authorized"] = False
    manifest.write_text(json.dumps(frozen))
    monkeypatch.setattr(pilot.subprocess, "check_output",
                        lambda *a, **k: pytest.fail("Review-only data must not start a run"))
    with pytest.raises(ValueError, match="not authorized"):
        pilot.run_trials(run, cache, "model", run / "proof.json", manifest)


def test_controller_refuses_runtime_profile_mismatch_before_authentication(trial_run, monkeypatch):
    run, cache, folder = trial_run
    manifest = folder / "frozen.json"
    frozen = json.loads(manifest.read_bytes())
    frozen["cases"][0]["runtime_profile"] = "sqlite"
    manifest.write_text(json.dumps(frozen))
    monkeypatch.setattr(pilot.subprocess, "check_output",
                        lambda *a, **k: pytest.fail("Mismatched runtime must not start a run"))
    with pytest.raises(ValueError, match="runtime differs"):
        pilot.run_trials(run, cache, "model", run / "proof.json", manifest)


def test_controller_keeps_budget_accounting_unknown_and_does_not_rerun(
        trial_run, monkeypatch):
    from scripts.real_skills_report import collect

    run, cache, frozen = trial_run
    calls = []
    usage = {"totalNanoAiu": 13, "tokenDetails": {
        key: {"tokenCount": 1} for key in ("input", "cache_read", "cache_write", "output")
    }}

    def compile(*args):
        calls.append("compile")
        call = args[3] / "call-1"
        call.mkdir()
        (call / "usage.json").write_text(json.dumps(usage))
        return {"verdict": "UNKNOWN", "outcome": "budget_exhausted",
                "accounting_complete": False, "calls": 2, "seconds": 1}

    def execute(*args):
        calls.append("execute")
        session = args[3] / "session"
        session.mkdir()
        (session / "usage.json").write_text(json.dumps(usage))
        return {"outcome": "verified_goal_achieved", "seconds": 1}

    monkeypatch.setattr(pilot, "compile_task", compile)
    monkeypatch.setattr(pilot, "execute_task", execute)
    for _ in range(2):
        pilot.run_trials(run, cache, "model", run / "proof.json")
    assert calls == ["compile", "execute"]
    model = collect(frozen, cache)["models"]["model"]
    assert model["verified_executions"] == 1
    assert model["four_way_counts"]["no_valid_prediction"] == 1
    compaction = model["reported_usage_including_failed_stages"]["compaction"]
    assert compaction["inclusive_input_tokens"] is None
    assert compaction["known_reported_nano_aiu"] == 13
    assert model["reported_usage_including_failed_stages"]["execution"]["reported_nano_aiu"] == 13


def test_controller_preserves_stage_evidence_when_native_accounting_is_missing(
        trial_run, monkeypatch):
    from scripts.real_skills_report import collect

    run, cache, frozen = trial_run
    monkeypatch.setattr(pilot, "compile_task",
                        lambda *a: {"verdict": "ACHIEVABLE", "seconds": 1})
    with pytest.raises(RuntimeError, match="usage receipt missing"):
        pilot.run_trials(run, cache, "model", run / "proof.json")
    failure = next(cache.rglob("failure.json"))
    evidence = json.loads(failure.read_text())
    assert evidence["outcome"] == "harness_error"
    assert evidence["stage_result"]["verdict"] == "ACHIEVABLE"
    result = json.loads(failure.with_name("result.json").read_text())
    assert result["verdict"] == "ACHIEVABLE" and result["usage"] is None
    report = collect(frozen, cache)
    assert report["trials"][0]["stages"]["compaction"]["verdict"] == "ACHIEVABLE"
    assert report["models"]["model"]["reported_usage_including_failed_stages"][
        "compaction"]["inclusive_input_tokens"] is None
    with pytest.raises(RuntimeError, match="refusing a paid rerun"):
        pilot.run_trials(run, cache, "model", run / "proof.json")
