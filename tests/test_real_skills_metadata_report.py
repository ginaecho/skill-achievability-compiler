import hashlib
import json

import pytest

from paper.figures.eval import make_real_skills_figure as figures
from scripts.real_skills_metadata import DESCRIPTION, METADATA, metadata_reference, verify_preview_metadata


@pytest.fixture
def metadata_collection(tmp_path, monkeypatch):
    original = b'<html><head><title>Report</title></head><body>{{model_name}}</body></html>'
    inputs = {"report.html": original}
    source = tmp_path / METADATA
    source.mkdir()
    (source / "report.html").write_bytes(original)
    folder = tmp_path / "collected" / "local" / "gpt-5.3-codex" / METADATA / "r1" / "execution"
    folder.mkdir(parents=True)
    actual = metadata_reference(inputs)
    (folder / "actual.html").write_bytes(actual)
    (folder / "verification.json").write_text(json.dumps(verify_preview_metadata(inputs, actual)))
    report = {"trials": [{"model": "gpt-5.3-codex", "repeat": 1,
                          "stages": {"execution": {"outcome": "verified_goal_achieved"}}}]}
    frozen = {"trial_namespace": "local", "models": ["gpt-5.3-codex"],
              "cases": [{"input_sha256": {"report.html": "unused"}}]}
    artifact = {"model": "gpt-5.3-codex", "repeat": 1,
                "actual_sha256": hashlib.sha256(actual).hexdigest(),
                "verification_sha256": hashlib.sha256((folder / "verification.json").read_bytes()).hexdigest()}
    audit = {"artifacts": [artifact], "active_manifest_sha256": "manifest", "summary_sha256": "summary"}
    audit_path = tmp_path / "completion_audit.json"
    audit_path.write_text(json.dumps(audit))
    quarantine = {
        "source": METADATA, "active_manifest_sha256": "manifest", "summary_sha256": "summary",
        "completion_audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "included_in_primary_outcomes": False, "sensitivity_is_primary_outcome": False,
        "frozen_description": DESCRIPTION, "exact_alternative_description": DESCRIPTION[:-1],
        "trials": [{**artifact, "observed_description": DESCRIPTION,
                    "frozen_with_period_passed": True, "exact_without_period_passed": False,
                    "either_punctuation_reading_passed": True}],
        "models": {"gpt-5.3-codex": {"frozen_with_period_passed": 1,
                                    "exact_without_period_passed": 0,
                                    "either_punctuation_reading_passed": 1}},
    }
    (tmp_path / "measurement_quarantine_20261124.json").write_text(json.dumps(quarantine))
    monkeypatch.setattr(figures, "verified_report", lambda *a, **k: (report, frozen, audit))
    return tmp_path, report, folder, artifact


def test_metadata_report_rechecks_the_retained_html_not_an_agent_claim(metadata_collection):
    pilot, report, _, _ = metadata_collection
    observed, _, audit = figures.metadata_report(pilot)
    assert observed is report
    assert audit["included_in_primary_outcomes"] is False


def test_metadata_report_cannot_admit_results_when_the_quarantine_record_is_missing(metadata_collection):
    pilot, _, _, _ = metadata_collection
    (pilot / "measurement_quarantine_20261124.json").unlink()
    with pytest.raises(FileNotFoundError):
        figures.metadata_report(pilot)


def test_metadata_report_recomputes_sensitivity_instead_of_trusting_its_totals(metadata_collection):
    pilot, _, _, _ = metadata_collection
    path = pilot / "measurement_quarantine_20261124.json"
    data = json.loads(path.read_bytes())
    data["models"]["gpt-5.3-codex"]["frozen_with_period_passed"] = 0
    path.write_text(json.dumps(data))
    with pytest.raises(AssertionError):
        figures.metadata_report(pilot)


@pytest.mark.parametrize("tamper", ["artifact", "verification", "consistent_false_claim"])
def test_metadata_report_rejects_changed_artifacts_and_self_consistent_false_claims(
        metadata_collection, tamper):
    pilot, _, folder, artifact = metadata_collection
    path = folder / "actual.html"
    if tamper != "verification":
        path.write_bytes(path.read_bytes().replace(b"noindex, nofollow", b"index, follow"))
    else:
        check = folder / "verification.json"
        check.write_bytes(check.read_bytes().replace(b'"access_control_verified": false',
                                                   b'"access_control_verified": true'))
    if tamper == "consistent_false_claim":
        artifact["actual_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        check = folder / "verification.json"
        claimed = json.loads(check.read_bytes())
        claimed["actual_sha256"] = artifact["actual_sha256"]
        check.write_text(json.dumps(claimed))
        artifact["verification_sha256"] = hashlib.sha256(check.read_bytes()).hexdigest()
    with pytest.raises(AssertionError):
        figures.metadata_report(pilot)
