import json

import pytest

from scripts.real_skills_report import combined_cohort_coverage, cohort_coverage, collect, snapshot


def test_report_retains_unknown_predictions_and_failed_stage_spend(tmp_path):
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    (pilot / "frozen.json").write_text(json.dumps({
        "scope": "pilot", "models": ["model"], "cases": [{"id": "skill"}], "repeats": 2,
    }))
    base = tmp_path / "pilot-trials" / "model" / "skill"
    for repeat, verdict in ((1, "INVALID"), (2, "IMPOSSIBLE")):
        for stage in ("compaction", "execution"):
            directory = base / f"r{repeat}" / stage
            directory.mkdir(parents=True)
            result = {"source": "skill", "model": "model", "repeat": repeat, "stage": stage}
            result["seconds"] = 1.5 if stage == "compaction" else None
            result["recovered_from_actual_tool_output"] = repeat == 1 and stage == "execution"
            result.update(verdict=verdict) if stage == "compaction" else result.update(
                outcome="verified_goal_not_achieved_with_runtime_evidence")
            (directory / "result.json").write_text(json.dumps(result))
    failed = base / "r1" / "compaction"
    (failed / "result.json").rename(failed / "failure.json")
    call = failed / "call-1"
    call.mkdir()
    (call / "usage.json").write_text(json.dumps({
        "totalNanoAiu": 13, "tokenDetails": {
            key: {"tokenCount": 1} for key in ("input", "cache_read", "cache_write", "output")
        },
    }))
    report = collect(pilot, tmp_path)
    model = report["models"]["model"]
    assert model["verified_executions"] == 2
    assert model["diagnostic_prediction_agreement"] == 0.5
    assert model["four_way_counts"]["no_valid_prediction"] == 1
    account = model["reported_usage_including_failed_stages"]["compaction"]
    assert account["reported_nano_aiu"] is None
    assert account["known_reported_nano_aiu"] == 13
    assert account["inclusive_input_tokens"] is None
    assert sum(account["known_disjoint_tokens"][key]
               for key in ("input", "cache_read", "cache_write")) == 3
    assert model["stage_timing_coverage"]["compaction"]["reported_trials"] == 1
    assert model["stage_timing_coverage"]["execution"]["missing_trials"] == 2
    assert report["status"] == "incomplete_pilot"
    assert len(report["failed_stages"]) == 1
    assert len(report["recovered_stages"]) == 1


@pytest.mark.parametrize(("filename", "content"), [
    ("actual.json", b'{"campaign":{}}'), ("actual.sql", b"SELECT 1;"),
    ("actual.ipynb", b'{"nbformat":4,"cells":[]}'),
    ("actual.md", b"# Reference index\n"),
    ("actual.csv", b"config_id,success_rate\nconfig_a,0.500000\n"),
    ("actual.html", b'<html><head><meta name="robots" content="noindex, nofollow"></head></html>'),
    ("filesystem_snapshot.json", b'{"old_path_lexists":true,"canonical_regular_file":true}'),
])
def test_snapshot_keeps_evidence_but_not_raw_native_identifiers(tmp_path, filename, content):
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    (pilot / "frozen.json").write_text(json.dumps({
        "models": ["model"], "cases": [{"id": "skill"}], "repeats": 1,
    }))
    folder = tmp_path / "pilot-trials" / "model" / "skill" / "r1" / "compaction"
    call = folder / "call-1"
    call.mkdir(parents=True)
    (folder / "result.json").write_text('{"verdict":"INVALID"}')
    (folder / filename).write_bytes(content)
    (call / "usage.json").write_text(json.dumps({
        "totalNanoAiu": 13, "tokenDetails": {}, "opaqueServiceId": "not-for-publication",
    }))
    (call / "receipt.json").write_text('{"opaqueServiceId":"not-for-publication"}')
    local = snapshot(pilot, tmp_path)
    copied = list(local.rglob("usage.json"))
    assert len(copied) == 1
    assert json.loads(copied[0].read_text())["totalNanoAiu"] == 13
    assert "opaqueServiceId" not in copied[0].read_text()
    assert not list(local.rglob("receipt.json"))
    assert next(local.rglob(filename)).read_bytes() == content
    assert snapshot(pilot, tmp_path) == local


def test_snapshot_retains_interrupted_spend_in_its_own_trial_namespace(tmp_path):
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    (pilot / "frozen.json").write_text(json.dumps({
        "scope": "pilot", "models": ["model"], "cases": [{"id": "skill"}],
        "repeats": 1, "trial_namespace": "corrected-trials",
    }))
    folder = tmp_path / "corrected-trials" / "model" / "skill" / "r1" / "compaction" / "call-1"
    folder.mkdir(parents=True)
    (folder / "usage.json").write_text(json.dumps({"totalNanoAiu": 13}))
    report = collect(pilot, snapshot(pilot, tmp_path))
    account = report["models"]["model"]["reported_usage_including_failed_stages"]["compaction"]
    assert account["reported_nano_aiu"] is None
    assert account["known_reported_nano_aiu"] == 13
    assert account["missing_token_details"] == 1
    assert account["inclusive_input_tokens"] is None
    assert account["output"] is None
    assert len(report["pending_stages"]) == 2


def test_snapshot_preserves_unaccounted_session_without_native_identifiers(tmp_path):
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    (pilot / "frozen.json").write_text(json.dumps({
        "scope": "pilot", "models": ["model"], "cases": [{"id": "skill"}], "repeats": 1,
    }))
    session = tmp_path / "pilot-trials" / "model" / "skill" / "r1" / "execution" / "session"
    session.mkdir(parents=True)
    (session / "receipt.json").write_text(json.dumps({
        "status": "timeout", "opaqueServiceId": "not-for-publication",
    }))
    local = snapshot(pilot, tmp_path)
    marker = next(local.rglob("usage_unavailable.json"))
    assert "opaqueServiceId" not in marker.read_text()
    assert not list(local.rglob("receipt.json"))
    account = collect(pilot, local)["models"]["model"][
        "reported_usage_including_failed_stages"]["execution"]
    assert account["usage_receipts"] == 0
    assert account["inclusive_input_tokens"] is None
    assert account["reported_nano_aiu"] is None
    assert len(account["unreported_stages"]) == 1
    (session / "usage.json").write_text(json.dumps({
        "totalNanoAiu": 13, "tokenDetails": {
            key: {"tokenCount": 1}
            for key in ("input", "cache_read", "cache_write", "output")
        },
    }))
    (session.parent / "result.json").write_text(json.dumps({
        "source": "skill", "model": "model", "repeat": 1, "stage": "execution",
        "outcome": "verified_goal_achieved", "seconds": 1,
        "usage": {"usage_files": 1},
    }))
    account = collect(pilot, snapshot(pilot, tmp_path))["models"]["model"][
        "reported_usage_including_failed_stages"]["execution"]
    assert account["inclusive_input_tokens"] == 3
    assert account["reported_nano_aiu"] == 13
    assert "unreported_stages" not in account


def test_budget_stop_with_no_native_metrics_is_unresolved_not_zero_cost(tmp_path):
    pilot = tmp_path / "pilot"
    pilot.mkdir()
    (pilot / "frozen.json").write_text(json.dumps({
        "scope": "pilot", "models": ["model"], "cases": [{"id": "skill"}], "repeats": 1,
    }))
    for stage in ("compaction", "execution"):
        folder = tmp_path / "pilot-trials" / "model" / "skill" / "r1" / stage
        folder.mkdir(parents=True)
        result = {"source": "skill", "model": "model", "repeat": 1, "stage": stage,
                  "seconds": 1}
        if stage == "compaction":
            result["verdict"] = "IMPOSSIBLE"
            result["usage"] = {"usage_files": 2}
            call = folder / "call-1"
            call.mkdir()
            (call / "usage.json").write_text(json.dumps({
                "totalNanoAiu": 13, "tokenDetails": {
                    key: {"tokenCount": 1}
                    for key in ("input", "cache_read", "cache_write", "output")
                },
            }))
        else:
            result.update(outcome="budget_exhausted", termination_reason="model_deadline")
        (folder / "result.json").write_text(json.dumps(result))
    report = collect(pilot, tmp_path)
    model = report["models"]["model"]
    assert model["verified_executions"] == 0
    assert model["four_way_counts"]["unresolved_execution"] == 1
    assert model["four_way_counts"]["blocked_goal_not_achieved"] == 0
    partial = model["reported_usage_including_failed_stages"]["compaction"]
    assert partial["reported_nano_aiu"] is None
    assert partial["known_reported_nano_aiu"] == 13
    assert partial["unreported_stages"][0]["reason"] == "missing_native_usage_receipts"
    account = model["reported_usage_including_failed_stages"]["execution"]
    assert account["inclusive_input_tokens"] is None
    assert account["output"] is None
    assert account["reported_nano_aiu"] is None
    assert account["unreported_stages"][0]["stage"] == "execution"
    assert account["unreported_stages"][0]["reason"] == "missing_native_usage_receipts"
    assert report["status"] == "incomplete_pilot"


def test_full_cohort_keeps_unmeasured_documents_out_of_observed_results():
    cases = [
        {"id": source, "repository": "public-project", "commit": "pinned",
         "path_in_repo": source, "sha256": source}
        for source in ("reviewed", "unreviewed")
    ]
    frozen = {"models": ["model"], "repeats": 5,
              "cases": [{"id": "reviewed", "skill_source": cases[0]}]}
    counts = {"possible_goal_achieved": 1, "possible_goal_not_achieved": 0,
              "blocked_goal_achieved": 0, "blocked_goal_not_achieved": 0,
              "no_valid_prediction": 0, "unresolved_execution": 0}
    report = {
        "models": {"model": {"verified_executions": 1, "four_way_counts": counts}},
        "trials": [{"source": "reviewed", "model": "model", "repeat": 1,
                    "stages": {"execution": {"outcome": "verified_goal_achieved"}}}],
    }
    coverage = cohort_coverage({"cases": cases}, frozen, report)
    assert coverage["planned_execution_trials"] == 10
    assert coverage["verified_execution_trials"] == 1
    assert coverage["unmeasured_execution_trials"] == 9
    assert coverage["models"]["model"]["observed_four_way_counts"] == counts
    assert coverage["documents"][1]["verified_executions"] == 0
    assert coverage["documents"][1]["unmeasured_executions"] == 5
    assert coverage["documents"][1]["reviewed_task"] is False
    assert coverage["full_cohort_accuracy"] is None
    assert coverage["full_cohort_tokens"] is None
    report["trials"].append(report["trials"][0])
    with pytest.raises(ValueError, match="duplicate trial"):
        cohort_coverage({"cases": cases}, frozen, report)
    frozen["cases"][0]["skill_source"] = {**cases[0], "sha256": "wrong-version"}
    with pytest.raises(ValueError, match="pinned cohort source"):
        cohort_coverage({"cases": cases}, frozen, report)


def test_coverage_combines_disjoint_freezes_and_normalizes_repository_identity():
    cases = [
        {"id": source, "repository": "NVIDIA/skills" if index == 0 else "nvidia/skills",
         "commit": "pinned",
         "path_in_repo": source, "sha256": source}
        for index, source in enumerate(("source-one", "source-two", "source-pending"))
    ]
    observations = []
    for index, source in enumerate(cases[:2]):
        manifest = {"models": ["model"], "repeats": 2,
                    "cases": [{"id": source["id"], "skill_source": source}]}
        counts = {key: 0 for key in (
            "possible_goal_achieved", "possible_goal_not_achieved",
            "blocked_goal_achieved", "blocked_goal_not_achieved",
            "no_valid_prediction", "unresolved_execution")}
        counts["possible_goal_achieved" if index == 0 else "no_valid_prediction"] = 1
        report = {"models": {"model": {"verified_executions": 1, "four_way_counts": counts}},
                  "trials": [{"source": source["id"], "model": "model", "repeat": 1,
                              "stages": {"execution": {"outcome": "verified_goal_achieved"}}}]}
        observations.append((manifest, report))
    combined = combined_cohort_coverage({"cases": cases}, observations)
    assert combined["repositories"] == 1
    assert combined["repository_commit_pairs"] == 1
    assert combined["reviewed_task_documents"] == 2
    assert combined["verified_execution_trials"] == 2
    assert combined["unmeasured_execution_trials"] == 4
    assert combined["models"]["model"]["observed_four_way_counts"]["no_valid_prediction"] == 1
    assert combined["full_cohort_accuracy"] is None and combined["full_cohort_tokens"] is None
    with pytest.raises(ValueError, match="Duplicate reviewed"):
        combined_cohort_coverage({"cases": cases}, [observations[0], observations[0]])
    observations[0][1]["models"]["model"]["verified_executions"] = 2
    observations[1][1]["models"]["model"]["verified_executions"] = 0
    with pytest.raises(ValueError, match="does not reconcile"):
        combined_cohort_coverage({"cases": cases}, observations)
    for _, report in observations:
        report["models"]["model"]["verified_executions"] = 1
    observations[1][0]["repeats"] = 3
    with pytest.raises(ValueError, match="different models or repeat"):
        combined_cohort_coverage({"cases": cases}, observations)


@pytest.mark.parametrize("quarantined", [None, 10])
def test_cohort_figure_displays_unknown_predictions_and_unresolved_attempts(monkeypatch, quarantined):
    pytest.importorskip("matplotlib")
    from matplotlib.figure import Figure
    from paper.figures.eval import make_real_skills_figure as figures

    cells = {}
    labels = []

    def capture(figure, *_args, **_kwargs):
        table = next(iter(figure.axes[0].tables))
        cells.update({key: cell.get_text().get_text()
                      for key, cell in table.get_celld().items()})
        labels.extend(text.get_text() for text in figure.texts)

    monkeypatch.setattr(Figure, "savefig", capture)
    figures.draw_cohort({
        **({"quarantined_execution_trials": quarantined} if quarantined is not None else {}),
        "source_count": 2, "repositories": 1, "repository_commit_pairs": 1,
        "reviewed_task_documents": 1, "documents_without_reviewed_task": 1,
        "verified_execution_trials": 2, "unmeasured_execution_trials": 2,
        "planned_execution_trials": 4, "planned_compaction_trials_before_retries": 4,
        "repeats_per_source_and_model": 2,
        "models": {"model": {
            "planned_executions": 4, "unmeasured_executions": 2,
            "observed_four_way_counts": {
                "possible_goal_achieved": 0, "blocked_goal_achieved": 0,
                "possible_goal_not_achieved": 0, "blocked_goal_not_achieved": 0,
                "no_valid_prediction": 2, "unresolved_execution": 1}}}})
    assert cells[(0, 5)] == "Unknown /\nverified"
    assert cells[(1, 5)] == "2"
    assert cells[(0, 6)] == "Unresolved\nattempts"
    assert cells[(1, 6)] == "1"
    assert any("completed trials quarantined" in label for label in labels) == (
        quarantined is not None)


@pytest.mark.parametrize(("outcome", "audited_unresolved", "accepted"), [
    ("budget_exhausted", 1, True),
    ("budget_exhausted", 0, False),
    ("harness_error", 1, False),
])
def test_figure_report_preserves_only_audited_terminal_budget_outcomes(
        tmp_path, monkeypatch, outcome, audited_unresolved, accepted):
    import hashlib

    from paper.figures.eval import make_real_skills_figure as figures

    pilot = tmp_path / "reviewed-symbolic"
    pilot.mkdir()
    manifest = {
        "models": ["model"], "cases": [{"id": "task", "input_sha256": {}}],
        "repeats": 1, "trial_namespace": "trials", "implementation_sha256": {},
    }
    tokens = {"input": 1, "cache_read": 0, "cache_write": 0, "output": 1}
    stages = {}
    for stage in ["compaction", "execution"]:
        folder = pilot / "collected" / "trials" / "model" / "task" / "r1" / stage / "session"
        folder.mkdir(parents=True)
        (folder / "usage.json").write_text(json.dumps({
            "tokenDetails": {key: {"tokenCount": value} for key, value in tokens.items()},
            "totalNanoAiu": 2,
        }))
        stages[stage] = {"usage": {"disjoint_tokens": tokens, "reported_nano_aiu": 2}}
    stages["execution"]["outcome"] = outcome
    report = {
        "status": "incomplete_pilot", "failed_stages": [], "pending_stages": [],
        "recovered_stages": [],
        "models": {"model": {
            "four_way_counts": {"unresolved_execution": 1},
            "reported_usage_including_failed_stages": {
                stage: {"inclusive_input_tokens": 1} for stage in stages},
        }},
        "trials": [{"model": "model", "source": "task", "repeat": 1, "stages": stages}],
    }
    for name, value in [("frozen.json", manifest), ("summary.json", report)]:
        (pilot / name).write_text(json.dumps(value))
    (pilot / "completion_audit.json").write_text(json.dumps({
        "active_manifest": "frozen.json", "unresolved_trials": audited_unresolved,
        "active_manifest_sha256": hashlib.sha256((pilot / "frozen.json").read_bytes()).hexdigest(),
        "summary_sha256": hashlib.sha256((pilot / "summary.json").read_bytes()).hexdigest(),
    }))
    (tmp_path / "implementation_retention_20261109.json").write_text(
        json.dumps({"source_sets": {}}))
    monkeypatch.setattr(figures, "MODELS", {"model": "Model"})
    monkeypatch.setattr(figures, "collect", lambda *_: report)
    if accepted:
        actual, _, _ = figures.verified_report(pilot, {"task"})
        assert actual["trials"][0]["stages"]["execution"]["outcome"] == "budget_exhausted"
        assert not list(pilot.rglob("verification.json"))
    else:
        with pytest.raises(AssertionError):
            figures.verified_report(pilot, {"task"})
