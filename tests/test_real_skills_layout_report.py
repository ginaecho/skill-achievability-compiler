import hashlib
import json

import pytest

from paper.figures.eval import make_real_skills_figure as figures
from scripts.real_skills_layout import LAYOUT, layout_reference, verify_layout_map


@pytest.fixture
def quarantined(tmp_path, monkeypatch):
    raw = ("note = '" + chr(0x2028) + chr(0x2029) + "'\n").encode()
    inputs = {"example.py": raw}
    case = {"id": LAYOUT, "input_sha256": {"example.py": hashlib.sha256(raw).hexdigest()}}
    (tmp_path / LAYOUT).mkdir()
    (tmp_path / LAYOUT / "example.py").write_bytes(raw)
    folder = tmp_path / "collected" / "local" / "stub" / LAYOUT / "r1" / "execution"
    folder.mkdir(parents=True)
    candidate = layout_reference(inputs)
    candidate["files"][0]["lines"] = 3
    actual = json.dumps(candidate).encode()
    verification = json.dumps(verify_layout_map(inputs, actual)).encode()
    (folder / "actual.json").write_bytes(actual)
    (folder / "verification.json").write_bytes(verification)
    report = {
        "trials": [
            {
                "model": "stub",
                "source": LAYOUT,
                "repeat": 1,
                "stages": {
                    "execution": {"outcome": "verified_goal_not_achieved_with_runtime_evidence"}
                },
            }
        ]
    }
    frozen = {"cases": [case], "trial_namespace": "local"}
    audit = {
        "active_manifest_sha256": "0" * 64,
        "paper_verified_outcome_count_increased": False,
        "frozen_byte_rule_goals_achieved": 0,
        "alternative_text_rule_goals_achieved": 1,
        "artifacts": [
            {
                "model": "stub",
                "repeat": 1,
                "outcome": "verified_goal_not_achieved_with_runtime_evidence",
                "actual_sha256": hashlib.sha256(actual).hexdigest(),
                "verification_sha256": hashlib.sha256(verification).hexdigest(),
                "frozen_byte_rule_passed": False,
                "alternative_text_rule_passed": True,
            }
        ],
    }
    decision = {
        "user_response_verbatim": "quarantine_with_sensitivity",
        "active_manifest_sha256": "0" * 64,
        "paid_reruns_authorized": False,
    }
    (tmp_path / "reporting_decision_20261123.json").write_text(json.dumps(decision))
    monkeypatch.setattr(figures, "verified_report", lambda *args, **kwargs: (report, frozen, audit))
    return tmp_path, report, audit, decision, folder


def test_quarantine_rechecks_both_rules_without_promoting_original_outcomes(quarantined):
    pilot, original, _, _, _ = quarantined
    before = json.dumps(original, sort_keys=True)
    report, _, audit = figures.quarantined_layout_report(pilot)
    assert report is original and json.dumps(report, sort_keys=True) == before
    assert audit["frozen_byte_rule_goals_achieved"] == 0
    assert audit["alternative_text_rule_goals_achieved"] == 1


@pytest.mark.parametrize("tamper", ["artifact", "decision", "sensitivity"])
def test_quarantine_refuses_changed_artifacts_or_silent_scoring_amendment(quarantined, tamper):
    pilot, _, audit, decision, folder = quarantined
    if tamper == "artifact":
        actual = folder / "actual.json"
        actual.write_bytes(actual.read_bytes() + b"\n")
    elif tamper == "decision":
        decision["user_response_verbatim"] = "amend_to_text_rescore"
        (pilot / "reporting_decision_20261123.json").write_text(json.dumps(decision))
    else:
        audit["artifacts"][0]["alternative_text_rule_passed"] = False
    with pytest.raises(AssertionError):
        figures.quarantined_layout_report(pilot)
