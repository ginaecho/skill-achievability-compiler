import hashlib
import json

import pytest

from paper.figures.eval import make_real_skills_figure as figures
from scripts.real_skills_instructions import INSTRUCTIONS, verify_instruction_migration


@pytest.fixture
def partial_instruction(tmp_path, monkeypatch):
    original = b"Keep these instructions.\n"
    inputs = {"CLAUDE.md": original}
    (tmp_path / INSTRUCTIONS).mkdir()
    (tmp_path / INSTRUCTIONS / "CLAUDE.md").write_bytes(original)
    continuation = tmp_path / "continuation_20261124.json"
    continuation.write_text("{}")
    folder = tmp_path / "collected" / "local" / "gpt-5.3-codex" / INSTRUCTIONS / "r1" / "execution"
    folder.mkdir(parents=True)
    state = {"old_path_lexists": True, "canonical_regular_file": True}
    (folder / "filesystem_snapshot.json").write_text(json.dumps(state))
    (folder / "actual.md").write_bytes(original)
    (folder / "verification.json").write_text(
        json.dumps(verify_instruction_migration(inputs, original, state))
    )
    incomplete = {
        "missing_token_details": 1,
        "inclusive_input_tokens": None,
        "output": None,
        "reported_nano_aiu": None,
        "unreported_stages": ["failure"],
    }
    report = {
        "models": {
            "gpt-5.6-sol": {"reported_usage_including_failed_stages": {"compaction": incomplete}}
        },
        "trials": [
            {
                "model": "gpt-5.3-codex",
                "repeat": 1,
                "stages": {
                    "execution": {"outcome": "verified_goal_not_achieved_with_runtime_evidence"}
                },
            }
        ],
    }
    failed = {"model": "gpt-5.6-sol", "source": INSTRUCTIONS, "repeat": 1, "stage": "compaction"}
    audit = {
        "retained_failed_stages": [failed, {**failed, "repeat": 2, "stage": "execution"}],
        "unstarted_stages": [{**failed, "stage": "execution"}]
        + [
            {**failed, "repeat": repeat, "stage": stage}
            for repeat in range(3, 6)
            for stage in ("compaction", "execution")
        ],
        "pairs_without_completed_stages": [
            {"model": "gpt-5.6-sol", "source": INSTRUCTIONS, "repeat": repeat}
            for repeat in (1, 3, 4, 5)
        ],
        "sandbox_failure_before_executor_inference": True,
        "failed_compaction_total_usage_known": False,
        "failed_stage_reported_zero_not_assumed_actual_zero": True,
        "continuation_sha256": hashlib.sha256(continuation.read_bytes()).hexdigest(),
        "artifacts": [
            {
                "model": "gpt-5.3-codex",
                "repeat": 1,
                **{
                    field: hashlib.sha256((folder / name).read_bytes()).hexdigest()
                    for name, field in [
                        ("actual.md", "actual_sha256"),
                        ("verification.json", "verification_sha256"),
                        ("filesystem_snapshot.json", "filesystem_snapshot_sha256"),
                    ]
                },
            }
        ],
    }
    frozen = {"trial_namespace": "local", "cases": [{"input_sha256": {"CLAUDE.md": "unused"}}]}
    monkeypatch.setattr(figures, "verified_report", lambda *a, **k: (report, frozen, audit))
    return tmp_path, report, folder


def test_instruction_report_retains_failed_transport_and_actual_old_entry(partial_instruction):
    pilot, report, _ = partial_instruction
    observed, _, _ = figures.instruction_report(pilot)
    assert observed is report
    assert (
        observed["models"]["gpt-5.6-sol"]["reported_usage_including_failed_stages"]["compaction"][
            "reported_nano_aiu"
        ]
        is None
    )


@pytest.mark.parametrize("recovery_recorded", [False, True])
def test_instruction_report_requires_explicit_recovery_of_the_startup_failure(
    partial_instruction, monkeypatch, recovery_recorded
):
    pilot, _, _ = partial_instruction
    original = figures.verified_report

    def resumed(*args, **kwargs):
        report, frozen, audit = original(*args, **kwargs)
        audit["retained_failed_stages"] = audit["retained_failed_stages"][:1]
        audit["preinference_startup_failure_resumed"] = recovery_recorded
        return report, frozen, audit

    monkeypatch.setattr(figures, "verified_report", resumed)
    if recovery_recorded:
        figures.instruction_report(pilot)
    else:
        with pytest.raises(AssertionError):
            figures.instruction_report(pilot)


@pytest.mark.parametrize("tamper", ["state", "actual", "usage"])
def test_instruction_report_refuses_changed_evidence_or_zero_filled_usage(
    partial_instruction, tamper
):
    pilot, report, folder = partial_instruction
    if tamper == "state":
        (folder / "filesystem_snapshot.json").write_text(
            json.dumps({"old_path_lexists": False, "canonical_regular_file": True})
        )
    elif tamper == "actual":
        (folder / "actual.md").write_bytes(b"Replacement instructions.\n")
    else:
        report["models"]["gpt-5.6-sol"]["reported_usage_including_failed_stages"]["compaction"][
            "reported_nano_aiu"
        ] = 0
    with pytest.raises(AssertionError):
        figures.instruction_report(pilot)
