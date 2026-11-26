import hashlib
import json
from pathlib import Path

import pytest

from paper.figures.eval import make_real_skills_figure as figures
from scripts.real_skills_sweep import SWEEP, sweep_reference, verify_sweep_summary


@pytest.fixture
def sweep_collection(tmp_path, monkeypatch):
    original = (Path(__file__).resolve().parents[1] / "runs" / "20261106_real_skills"
                / "reviewed-sweep" / SWEEP / "summary_review.csv").read_bytes()
    inputs = {"summary_review.csv": original}
    source = tmp_path / SWEEP
    source.mkdir()
    (source / "summary_review.csv").write_bytes(original)
    folder = tmp_path / "collected" / "local" / "gpt-5.3-codex" / SWEEP / "r1" / "execution"
    folder.mkdir(parents=True)
    actual = sweep_reference(inputs)
    (folder / "actual.csv").write_bytes(actual)
    (folder / "verification.json").write_text(json.dumps(verify_sweep_summary(inputs, actual)))
    outcome = "verified_goal_achieved"
    report = {"trials": [{"model": "gpt-5.3-codex", "repeat": 1,
                          "stages": {"execution": {"outcome": outcome}}}]}
    frozen = {"trial_namespace": "local", "cases": [{
        "target": "/work/sweep_summary.csv", "input_sha256": {"summary_review.csv": "unused"}}]}
    artifact = {"model": "gpt-5.3-codex", "repeat": 1, "outcome": outcome,
                "actual_sha256": hashlib.sha256(actual).hexdigest(),
                "verification_sha256": hashlib.sha256((folder / "verification.json").read_bytes()).hexdigest()}
    audit = {"artifacts": [artifact]}
    monkeypatch.setattr(figures, "verified_report", lambda *a, **k: (report, frozen, audit))
    return tmp_path, report, folder, artifact


def test_sweep_report_replays_actual_csv_instead_of_trusting_a_success_claim(sweep_collection):
    pilot, report, _, _ = sweep_collection
    observed, _, _ = figures.sweep_report(pilot)
    assert observed is report


@pytest.mark.parametrize("tamper", ["artifact", "verification", "consistent_false_claim", "missing_artifact"])
def test_sweep_report_rejects_changed_or_missing_evidence(sweep_collection, tamper):
    pilot, _, folder, artifact = sweep_collection
    path = folder / "actual.csv"
    if tamper == "missing_artifact":
        path.unlink()
    elif tamper != "verification":
        path.write_bytes(path.read_bytes().replace(b"0.800000", b"0.500000", 1))
    else:
        check = folder / "verification.json"
        check.write_bytes(check.read_bytes().replace(b'"expected_rows": 9', b'"expected_rows": 10'))
    if tamper == "consistent_false_claim":
        artifact["actual_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        check = folder / "verification.json"
        claimed = json.loads(check.read_bytes())
        claimed["actual_sha256"] = artifact["actual_sha256"]
        check.write_text(json.dumps(claimed))
        artifact["verification_sha256"] = hashlib.sha256(check.read_bytes()).hexdigest()
    with pytest.raises(AssertionError):
        figures.sweep_report(pilot)
