r"""Rebuild full-cohort Figure 3, pilot Figure 4, and receipt-derived LaTeX numbers.

Run from the repository root: python paper\figures\eval\make_real_skills_figure.py
No model calls, downloads, or execution of benchmark inputs are performed.
"""
import hashlib
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from scripts.real_skills_report import combined_cohort_coverage, collect  # noqa: E402
from scripts.real_skills_caption import CAPTION  # noqa: E402
from scripts.real_skills_index import INDEX  # noqa: E402
from scripts.real_skills_metadata import DESCRIPTION, METADATA, verify_preview_metadata  # noqa: E402
from scripts.real_skills_sweep import SWEEP, verify_sweep_summary  # noqa: E402
from scripts.real_skills_instructions import INSTRUCTIONS, verify_instruction_migration  # noqa: E402
from scripts.real_skills_layout import LAYOUT, layout_reference, verify_layout_map  # noqa: E402
from scripts.real_skills_notebook import NOTEBOOK  # noqa: E402
from scripts.real_skills_symbolic import SYMBOLIC  # noqa: E402
from scripts.real_skills_verifiers import (  # noqa: E402
    BATCH, PALETTE, PROPERTY, SQL_TASKS, _verify_json, palette_reference,
)

OUT = Path(__file__).resolve().parent
PILOT = ROOT / "runs" / "20261106_real_skills" / "pilot-guarded"
EXTENSION = PILOT.parent / "reviewed-tasks"
MUTATION_TASK = "trailofbits__skills__mutation-testing"
MODELS = {"gpt-5.3-codex": "Codex", "gpt-5.6-sol": "Sol"}
TASKS = {
    "CaliLuke__skills__fowler-refactoring": ("Refactor", "Writable refactoring"),
    "AgentCTO__claude-skills__incremental-writes": ("Protected", "Protected-file edit"),
}
OUTCOMES = (
    ("possible_goal_achieved", "Possible / goal achieved", "#227850"),
    ("blocked_goal_not_achieved", "Blocked / goal not achieved", "#1F3A5F"),
    ("possible_goal_not_achieved", "Possible / goal not achieved", "#C98A18"),
    ("blocked_goal_achieved", "Blocked / goal achieved", "#B23434"),
)


def verified_report(pilot=PILOT, tasks=TASKS, *, summary_name="summary.json",
                    audit_name="completion_audit.json", allow_incomplete=False):
    stored = json.loads((pilot / summary_name).read_bytes())
    audit = json.loads((pilot / audit_name).read_bytes())
    assert hashlib.sha256((pilot / summary_name).read_bytes()).hexdigest() == (
        audit["summary_sha256"])
    frozen = json.loads((pilot / audit["active_manifest"]).read_bytes())
    assert hashlib.sha256((pilot / audit["active_manifest"]).read_bytes()).hexdigest() == (
        audit["active_manifest_sha256"])
    retention = json.loads((pilot.parent / "implementation_retention_20261109.json").read_bytes())
    for digest in frozen["implementation_sha256"].values():
        retained = pilot.parent / "implementation-objects" / digest
        if pilot.name != "pilot-guarded":
            assert hashlib.sha256(retained.read_bytes()).hexdigest() == digest
    if pilot.name in retention["source_sets"]:
        objects = retention["source_sets"][pilot.name]
        assert {name: item["sha256"] for name, item in objects.items()} == (
            frozen["implementation_sha256"])
        for item in objects.values():
            path = pilot.parent / "implementation-objects" / item["sha256"]
            assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    report = collect(pilot, pilot / "collected")
    for key in ("models", "trials", "recovered_stages"):
        assert report[key] == stored[key], f"Retained evidence differs from summary: {key}"
    unresolved = sum(model["four_way_counts"]["unresolved_execution"]
                     for model in report["models"].values())
    assert unresolved == audit.get("unresolved_trials", 0)
    assert report["status"] == stored["status"]
    missing_pairs = audit.get("pairs_without_completed_stages", []) if allow_incomplete else []
    if allow_incomplete:
        assert report["status"] == "incomplete_pilot"
        assert report["pending_stages"] == audit["unstarted_stages"]
        assert report["failed_stages"] == audit["retained_failed_stages"]
    else:
        assert report["status"] == ("incomplete_pilot" if unresolved else "complete_pilot")
        assert not report["pending_stages"] and not report["failed_stages"]
        assert all(account["inclusive_input_tokens"] is not None
                   for model in report["models"].values()
                   for account in model["reported_usage_including_failed_stages"].values())
    assert set(frozen["models"]) == set(MODELS)
    assert {case["id"] for case in frozen["cases"]} == set(tasks)
    expected_pairs = {(model, case["id"], repeat) for model in frozen["models"]
                      for case in frozen["cases"] for repeat in range(1, frozen["repeats"] + 1)}
    missing = {(row["model"], row["source"], row["repeat"]) for row in missing_pairs}
    assert len(missing) == len(missing_pairs) and missing <= expected_pairs
    observed_pairs = {(row["model"], row["source"], row["repeat"]) for row in report["trials"]}
    assert len(observed_pairs) == len(report["trials"])
    assert observed_pairs == expected_pairs - missing
    for case in frozen["cases"]:
        inputs = case["input_sha256"]
        expected = inputs if isinstance(inputs, dict) else {"input.py": inputs}
        for name, digest in expected.items():
            assert hashlib.sha256((pilot / case["id"] / name).read_bytes()).hexdigest() == digest
    for trial in report["trials"]:
        base = (pilot / "collected" / frozen["trial_namespace"] / trial["model"]
                / trial["source"] / f"r{trial['repeat']}")
        for stage, result in trial["stages"].items():
            folder = base / stage
            receipts = (list(folder.glob("call-*/usage.json"))
                        + list(folder.glob("session/usage.json")))
            usage = [json.loads(path.read_bytes()) for path in receipts]
            assert result["usage"]["disjoint_tokens"] == {
                key: sum(u["tokenDetails"][key]["tokenCount"] for u in usage)
                for key in ("input", "cache_read", "cache_write", "output")
            }
            assert result["usage"]["reported_nano_aiu"] == sum(u["totalNanoAiu"] for u in usage)
        outcome = trial["stages"].get("execution", {}).get("outcome")
        if outcome is None:
            assert allow_incomplete
            continue
        if outcome not in {
                "verified_goal_achieved", "verified_goal_not_achieved_with_runtime_evidence"}:
            assert outcome == "budget_exhausted" and unresolved > 0
            assert not (base / "execution" / "verification.json").exists()
            continue
        verification = json.loads((base / "execution" / "verification.json").read_bytes())
        assert verification["passed"] == (
            outcome == "verified_goal_achieved")
    return report, frozen, audit


def instruction_report(pilot=None):
    continued = PILOT.parent / "reviewed-instructions-continued"
    pilot = pilot or (continued if (continued / "completion_audit.json").is_file()
                      else PILOT.parent / "reviewed-instructions")
    resumed = (pilot / "completion_audit.json").is_file()
    report, frozen, audit = verified_report(
        pilot, {INSTRUCTIONS},
        summary_name="summary.json" if resumed else "summary_partial_20261124.json",
        audit_name="completion_audit.json" if resumed else "partial_audit_20261124.json",
        allow_incomplete=True)
    failed = {"model": "gpt-5.6-sol", "source": INSTRUCTIONS, "repeat": 1,
              "stage": "compaction"}
    startup_failure = {**failed, "repeat": 2, "stage": "execution"}
    assert failed in audit["retained_failed_stages"]
    assert all(row in (failed, startup_failure) for row in audit["retained_failed_stages"])
    assert startup_failure in audit["retained_failed_stages"] or audit.get(
        "preinference_startup_failure_resumed") is True
    assert audit["sandbox_failure_before_executor_inference"] is True
    assert audit["failed_compaction_total_usage_known"] is False
    assert audit["failed_stage_reported_zero_not_assumed_actual_zero"] is True
    assert hashlib.sha256((pilot / "continuation_20261124.json").read_bytes()).hexdigest() == (
        audit["continuation_sha256"])
    for name, digest in audit.get("continuation_records", {}).items():
        assert hashlib.sha256((pilot / name).read_bytes()).hexdigest() == digest
    usage = report["models"]["gpt-5.6-sol"]["reported_usage_including_failed_stages"]
    incomplete = usage["compaction"]
    assert incomplete["missing_token_details"] == 1
    assert incomplete["inclusive_input_tokens"] is None and incomplete["output"] is None
    assert incomplete["reported_nano_aiu"] is None and incomplete["unreported_stages"]
    case, = frozen["cases"]
    inputs = {name: (pilot / INSTRUCTIONS / name).read_bytes() for name in case["input_sha256"]}
    artifacts = {(row["model"], row["repeat"]): row for row in audit["artifacts"]}
    assert len(artifacts) == len(audit["artifacts"]) == sum(
        "execution" in trial["stages"] for trial in report["trials"])
    for trial in report["trials"]:
        if "execution" not in trial["stages"]:
            continue
        folder = (pilot / "collected" / frozen["trial_namespace"] / trial["model"]
                  / INSTRUCTIONS / f"r{trial['repeat']}" / "execution")
        if trial["stages"]["execution"]["outcome"] == "budget_exhausted":
            continue
        artifact = artifacts[trial["model"], trial["repeat"]]
        for name, field in (("filesystem_snapshot.json", "filesystem_snapshot_sha256"),
                            ("verification.json", "verification_sha256")):
            assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == artifact[field]
        state = json.loads((folder / "filesystem_snapshot.json").read_bytes())
        path = folder / "actual.md"
        actual = path.read_bytes() if path.exists() else None
        assert (hashlib.sha256(actual).hexdigest() if actual is not None else None) == (
            artifact["actual_sha256"])
        verification = json.loads((folder / "verification.json").read_bytes())
        reproduced = verify_instruction_migration(inputs, actual, state)
        if "snapshot_error" in verification:
            assert actual is None and state["canonical_regular_file"]
            assert verification["snapshot_error"]
            reproduced["snapshot_error"] = verification["snapshot_error"]
        assert verification == reproduced
    return report, frozen, audit


def metadata_report(pilot=None):
    pilot = pilot or PILOT.parent / "reviewed-metadata"
    report, frozen, audit = verified_report(pilot, {METADATA})
    case, = frozen["cases"]
    inputs = {name: (pilot / METADATA / name).read_bytes() for name in case["input_sha256"]}
    artifacts = {(row["model"], row["repeat"]): row for row in audit["artifacts"]}
    verified = [trial for trial in report["trials"] if trial["stages"]["execution"]["outcome"]
                in {"verified_goal_achieved", "verified_goal_not_achieved_with_runtime_evidence"}]
    assert len(artifacts) == len(audit["artifacts"]) == len(verified)
    checks = {}
    for trial in verified:
        folder = (pilot / "collected" / frozen["trial_namespace"] / trial["model"]
                  / METADATA / f"r{trial['repeat']}" / "execution")
        artifact = artifacts[trial["model"], trial["repeat"]]
        raw = (folder / "verification.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == artifact["verification_sha256"]
        verification = json.loads(raw)
        checks[trial["model"], trial["repeat"]] = verification
        path = folder / "actual.html"
        if path.exists():
            actual = path.read_bytes()
            assert hashlib.sha256(actual).hexdigest() == artifact["actual_sha256"]
            assert verify_preview_metadata(inputs, actual) == verification
        else:
            assert artifact["actual_sha256"] is None and not verification["passed"]
            assert verification["kind"] == "unavailable_deliverable"
            assert verification["target"] == "/work/report.html" and verification["error"]
    quarantine_raw = (pilot / "measurement_quarantine_20261124.json").read_bytes()
    quarantine = json.loads(quarantine_raw)
    assert quarantine["source"] == METADATA
    assert quarantine["active_manifest_sha256"] == audit["active_manifest_sha256"]
    assert quarantine["summary_sha256"] == audit["summary_sha256"]
    assert quarantine["completion_audit_sha256"] == hashlib.sha256(
        (pilot / "completion_audit.json").read_bytes()).hexdigest()
    assert quarantine["included_in_primary_outcomes"] is False
    assert quarantine["sensitivity_is_primary_outcome"] is False
    assert quarantine["frozen_description"] == DESCRIPTION
    assert quarantine["exact_alternative_description"] == DESCRIPTION[:-1]
    rows = quarantine["trials"]
    assert len(rows) == len(artifacts)
    assert {(row["model"], row["repeat"]) for row in rows} == set(artifacts)
    for row in rows:
        identity = row["model"], row["repeat"]
        artifact, check = artifacts[identity], checks[identity]
        for key in ("actual_sha256", "verification_sha256"):
            assert row[key] == artifact[key]
        assert check["original_bytes_preserved"]
        assert check["metadata"]["robots"] == "noindex, nofollow"
        observed = check["metadata"]["description"]
        assert row["observed_description"] == observed
        assert row["frozen_with_period_passed"] is check["passed"]
        assert row["exact_without_period_passed"] is (observed == DESCRIPTION[:-1])
        assert row["either_punctuation_reading_passed"] is (
            observed in {DESCRIPTION, DESCRIPTION[:-1]})
    totals = {model: {key: sum(row[key] for row in rows if row["model"] == model)
                      for key in ("frozen_with_period_passed", "exact_without_period_passed",
                                  "either_punctuation_reading_passed")}
              for model in frozen["models"]}
    assert quarantine["models"] == totals
    audit = {**audit, "included_in_primary_outcomes": False,
             "quarantine_audit_sha256": hashlib.sha256(quarantine_raw).hexdigest(),
             "sensitivity_models": totals}
    return report, frozen, audit


def sweep_report(pilot=None):
    pilot = pilot or PILOT.parent / "reviewed-sweep"
    report, frozen, audit = verified_report(pilot, {SWEEP})
    case, = frozen["cases"]
    inputs = {name: (pilot / SWEEP / name).read_bytes() for name in case["input_sha256"]}
    artifacts = {(row["model"], row["repeat"]): row for row in audit["artifacts"]}
    verified = [trial for trial in report["trials"] if trial["stages"]["execution"]["outcome"]
                in {"verified_goal_achieved", "verified_goal_not_achieved_with_runtime_evidence"}]
    assert len(artifacts) == len(audit["artifacts"]) == len(verified)
    for trial in verified:
        folder = (pilot / "collected" / frozen["trial_namespace"] / trial["model"]
                  / SWEEP / f"r{trial['repeat']}" / "execution")
        artifact = artifacts[trial["model"], trial["repeat"]]
        assert artifact["outcome"] == trial["stages"]["execution"]["outcome"]
        raw = (folder / "verification.json").read_bytes()
        assert hashlib.sha256(raw).hexdigest() == artifact["verification_sha256"]
        verification = json.loads(raw)
        path = folder / "actual.csv"
        if path.exists():
            actual = path.read_bytes()
            assert hashlib.sha256(actual).hexdigest() == artifact["actual_sha256"]
            assert verify_sweep_summary(inputs, actual) == verification
        else:
            assert artifact["actual_sha256"] is None and not verification["passed"]
            assert verification["kind"] == "unavailable_deliverable"
            assert verification["target"] == case["target"] and verification["error"]
    return report, frozen, audit


def quarantined_layout_report(pilot=None):
    pilot = pilot or PILOT.parent / "reviewed-layout"
    report, frozen, audit = verified_report(
        pilot, {LAYOUT}, summary_name="summary_frozen_oracle.json",
        audit_name="frozen_oracle_audit.json")
    decision = json.loads((pilot / "reporting_decision_20261123.json").read_bytes())
    assert decision["user_response_verbatim"] == "quarantine_with_sensitivity"
    assert decision["active_manifest_sha256"] == audit["active_manifest_sha256"]
    assert not decision["paid_reruns_authorized"]
    assert not audit["paper_verified_outcome_count_increased"]
    case, = frozen["cases"]
    inputs = {name: (pilot / case["id"] / name).read_bytes() for name in case["input_sha256"]}
    alternative = layout_reference(inputs)
    lengths = {row["name"]: len(inputs[row["name"]].decode("utf-8").splitlines())
               for row in alternative["files"]}
    for row in alternative["files"]:
        row["lines"] = lengths[row["name"]]
    for key in ("prefix_clusters", "import_tree_clusters"):
        for row in alternative[key]:
            row["lines"] = sum(lengths[name] for name in row["files"])
    artifacts = {(row["model"], row["repeat"]): row for row in audit["artifacts"]}
    assert len(artifacts) == len(audit["artifacts"]) == len(report["trials"])
    byte_passed = text_passed = 0
    for trial in report["trials"]:
        folder = (pilot / "collected" / frozen["trial_namespace"] / trial["model"]
                  / trial["source"] / f"r{trial['repeat']}" / "execution")
        actual = (folder / "actual.json").read_bytes()
        verification_raw = (folder / "verification.json").read_bytes()
        verification = json.loads(verification_raw)
        row = artifacts[trial["model"], trial["repeat"]]
        assert row["outcome"] == trial["stages"]["execution"]["outcome"]
        assert hashlib.sha256(actual).hexdigest() == row["actual_sha256"]
        assert hashlib.sha256(verification_raw).hexdigest() == row["verification_sha256"]
        assert verification == verify_layout_map(inputs, actual)
        text_check = _verify_json(alternative, actual, "postcollection_text_sensitivity")
        assert verification["passed"] == row["frozen_byte_rule_passed"]
        assert text_check["passed"] == row["alternative_text_rule_passed"]
        byte_passed += verification["passed"]
        text_passed += text_check["passed"]
    assert byte_passed == audit["frozen_byte_rule_goals_achieved"]
    assert text_passed == audit["alternative_text_rule_goals_achieved"]
    return report, frozen, audit


def full_cohort_report(report, frozen, audit, extensions, quarantined):
    cohort = json.loads((PILOT.parent / "cohort.json").read_bytes())
    protocol = json.loads((PILOT.parent / "protocol.json").read_bytes())
    recovery = json.loads((PILOT.parent / "source_recovery_audit.json").read_bytes())
    assert protocol["models"] == frozen["models"]
    assert protocol["repeats_per_skill_and_model"] == frozen["repeats"] == cohort["repeats"]
    coverage = combined_cohort_coverage(
        cohort, [(frozen, report)] + [
            (manifest, observed) for observed, manifest, extension_audit in extensions.values()
            if extension_audit.get("included_in_primary_outcomes", True)])
    layout, layout_frozen, layout_audit = quarantined
    combined_cohort_coverage(cohort, [(layout_frozen, layout)])
    quarantined_ids = {case["id"] for case in layout_frozen["cases"]}
    quarantined_trials = list(layout["trials"])
    additional_quarantines = {}
    for name, (observed, manifest, extension_audit) in extensions.items():
        if extension_audit.get("included_in_primary_outcomes", True):
            continue
        combined_cohort_coverage(cohort, [(manifest, observed)])
        quarantined_ids.update(case["id"] for case in manifest["cases"])
        quarantined_trials.extend(observed["trials"])
        additional_quarantines[name] = {
            "sources": [case["id"] for case in manifest["cases"]],
            "summary_sha256": extension_audit["summary_sha256"],
            "quarantine_audit_sha256": extension_audit["quarantine_audit_sha256"],
            "sensitivity_models": extension_audit["sensitivity_models"],
            "included_in_primary_outcomes": False,
        }
    for document in coverage["documents"]:
        if document["id"] in quarantined_ids:
            assert not document["reviewed_task"] and not document["verified_executions"]
            document["task_review_completed_but_outcomes_quarantined"] = True
            document["quarantined_execution_trials"] = sum(
                trial["source"] == document["id"] for trial in quarantined_trials)
    coverage["quarantined_execution_trials"] = len(quarantined_trials)
    coverage["quarantined_task_documents"] = len(quarantined_ids)
    coverage["frozen_reviewed_task_documents"] = (
        coverage["reviewed_task_documents"] + len(quarantined_ids))
    coverage["documents_without_frozen_reviewed_task"] = (
        coverage["documents_without_reviewed_task"] - len(quarantined_ids))
    layout_path = PILOT.parent / "reviewed-layout"
    coverage["quarantine"] = {
        "sources": sorted(quarantined_ids), "included_in_primary_outcomes": False,
        "layout_source": LAYOUT,
        "additional_source_quarantines": additional_quarantines,
        "frozen_byte_rule_goals_achieved": layout_audit["frozen_byte_rule_goals_achieved"],
        "postcollection_text_rule_goals_achieved": (
            layout_audit["alternative_text_rule_goals_achieved"]),
        "summary_sha256": layout_audit["summary_sha256"],
        "audit_sha256": hashlib.sha256(
            (layout_path / "frozen_oracle_audit.json").read_bytes()).hexdigest(),
        "decision_sha256": hashlib.sha256(
            (layout_path / "reporting_decision_20261123.json").read_bytes()).hexdigest(),
    }
    identity = json.loads((PILOT.parent / "repository_identity_audit_20261123.json").read_bytes())
    assert coverage["source_count"] == recovery["source_count"]
    assert identity["cohort_sha256"] == hashlib.sha256(
        (PILOT.parent / "cohort.json").read_bytes()).hexdigest()
    assert identity["source_recovery_audit_sha256"] == hashlib.sha256(
        (PILOT.parent / "source_recovery_audit.json").read_bytes()).hexdigest()
    for key, spelling_key in (("repositories", "repository_spellings"),
                              ("repository_commit_pairs", "repository_commit_pair_spellings")):
        assert coverage[spelling_key] == recovery[key] == (
            identity["historical_spelling_counts"][key])
        assert coverage[key] == identity["normalized_identity_counts"][key]
    assert sum(recovery["statuses"][key] for key in (
        "recovered", "recovered_with_withheld_files")) == coverage["source_count"]
    coverage["evidence_sha256"] = {
        name: hashlib.sha256((PILOT.parent / name).read_bytes()).hexdigest()
        for name in ("cohort.json", "protocol.json", "source_recovery_audit.json",
                     "repository_identity_audit_20261123.json")
    }
    coverage["evidence_sha256"].update(
        pilot_summary=audit["summary_sha256"], pilot_manifest=audit["active_manifest_sha256"])
    for name, (_, _, extension_audit) in extensions.items():
        coverage["evidence_sha256"][name.lower() + "_summary"] = extension_audit["summary_sha256"]
        coverage["evidence_sha256"][name.lower() + "_manifest"] = (
            extension_audit["active_manifest_sha256"])
    coverage["interpretation"] = (
        "All cohort documents are enumerated. Observed outcomes and costs come only from the "
        "retained corrected pilot and separately frozen public-input source extensions; "
        "unmeasured trials are not failures, refutations or zero costs. "
        "Historical outcomes are not relabeled as new-protocol measurements.")
    coverage["interpretation"] += (
        " Reviewed-task flags and counts above refer to admitted primary evidence, not all "
        "completed task reviews. The separately identified layout task was reviewed and "
        "executed but remains quarantined for ambiguous line-count semantics. Its ten "
        "trials remain in the original denominator and outside primary four-way counts; "
        "all native usage and timings are reported separately, not discarded or zeroed.")
    if additional_quarantines:
        coverage["interpretation"] += (
            " Additional source quarantines and their exact interpretation sensitivities are "
            "listed explicitly above. Their trials also stay outside primary counts and "
            "inside the original unmeasured denominator; none is silently rescored or rerun.")
    (PILOT.parent / "full_cohort_coverage.json").write_text(
        json.dumps(coverage, indent=2) + "\n", encoding="utf-8", newline="\n")
    return coverage


def write_numbers(report, frozen, audit, coverage, extensions, quarantined):
    numbers = {}
    source_count = coverage["source_count"]
    numbers.update(SourceCount=source_count, TaskCount=len(TASKS), Repeats=frozen["repeats"],
                   RemainingTasks=source_count - len(TASKS), Executions=len(report["trials"]),
                   Inferences=sum(audit["native_inference_counts"].values()),
                   Receipts=sum(
                       stage["usage_receipts"] for model in report["models"].values()
                       for stage in model["reported_usage_including_failed_stages"].values()))
    for model, short in MODELS.items():
        rows = [t for t in report["trials"] if t["model"] == model]
        measured = report["models"][model]["reported_usage_including_failed_stages"]
        counts = report["models"][model]["four_way_counts"]
        for key, name in (
            ("possible_goal_achieved", "TruePossible"),
            ("blocked_goal_not_achieved", "TrueBlocked"),
            ("possible_goal_not_achieved", "MissedBlocked"),
            ("blocked_goal_achieved", "FalseBlocked"),
        ):
            numbers[short + name] = counts[key]
        for stage, label in (("compaction", "Compile"), ("execution", "Execute")):
            usage = measured[stage]
            assert usage["missing_token_details"] == 0
            for key, suffix in (("inclusive_input_tokens", "Input"), ("output", "Output"),
                                ("cache_read", "CacheRead"), ("cache_write", "CacheWrite"),
                                ("input", "Uncached"), ("reported_nano_aiu", "NanoAiu")):
                numbers[short + label + suffix] = usage[key]
        numbers[short + "CheckerMs"] = 1000 * statistics.median(
            t["stages"]["compaction"]["validation_seconds"] for t in rows)
        for source, (task, _) in TASKS.items():
            trials = [t for t in rows if t["source"] == source]
            assert sorted(t["repeat"] for t in trials) == list(range(1, frozen["repeats"] + 1))
            permission_trials = nonzero_trials = 0
            for trial in trials:
                tools = (PILOT / "collected" / frozen["trial_namespace"] / model
                         / source / f"r{trial['repeat']}" / "execution" / "tools.jsonl")
                results = [r for line in tools.read_text().splitlines()
                           if (r := json.loads(line))["type"] == "tool_result"]
                permission_trials += any("PermissionError" in r["output"] for r in results)
                nonzero = sum(r["exit_code"] != 0 for r in results)
                assert nonzero == trial["stages"]["execution"]["tool_errors"]
                nonzero_trials += nonzero > 0
            numbers[short + task + "PermissionTrials"] = permission_trials
            numbers[short + task + "NonzeroTrials"] = nonzero_trials
            for stage, label in (("compaction", "Compile"), ("execution", "Execute")):
                stages = [t["stages"][stage] for t in trials]
                times = [s["seconds"] for s in stages if s["seconds"] is not None]
                numbers[short + task + label + "Tokens"] = statistics.median(
                    sum(s["usage"]["disjoint_tokens"].values()) for s in stages)
                numbers[short + task + label + "Seconds"] = statistics.median(times)
                numbers[short + task + label + "TimingN"] = len(times)
    lines = ["% Generated by make_real_skills_figure.py; do not edit.",
             f"% Retained summary SHA256: {audit['summary_sha256']}",
             f"% Active manifest SHA256: {audit['active_manifest_sha256']}"]
    for key, value in numbers.items():
        text = (f"{value:.1f}" if isinstance(value, float) and not value.is_integer()
                else f"{int(value):,}")
        lines.append(r"\newcommand{\Pilot" + key + "}{" + text.replace(",", "{,}") + "}")
    for prefix, (extension, extension_frozen, extension_audit) in {
            **extensions, "Layout": quarantined}.items():
        extension_numbers = {"Executions": sum(
            "execution" in trial["stages"] for trial in extension["trials"])}
        for model, short in MODELS.items():
            rows = [t for t in extension["trials"] if t["model"] == model]
            for case in extension_frozen["cases"]:
                absent = extension_audit.get("pairs_without_completed_stages", [])
                missing = {row["repeat"] for row in absent
                           if row["model"] == model and row["source"] == case["id"]}
                assert sorted(t["repeat"] for t in rows if t["source"] == case["id"]) == (
                    [repeat for repeat in range(1, extension_frozen["repeats"] + 1)
                     if repeat not in missing])
            counts = extension["models"][model]["four_way_counts"]
            extension_numbers[short + "Achieved"] = (
                counts["possible_goal_achieved"] + counts["blocked_goal_achieved"])
            extension_numbers[short + "Refuted"] = (
                counts["blocked_goal_achieved"] + counts["blocked_goal_not_achieved"])
            for key, suffix in (
                ("possible_goal_achieved", "PossibleAchieved"),
                ("possible_goal_not_achieved", "PossibleNotAchieved"),
                ("blocked_goal_achieved", "BlockedAchieved"),
                ("blocked_goal_not_achieved", "BlockedNotAchieved"),
                ("no_valid_prediction", "Unknown"), ("unresolved_execution", "Unresolved"),
            ):
                extension_numbers[short + suffix] = counts[key]
            for stage, label in (("compaction", "Compile"), ("execution", "Execute")):
                usage = extension["models"][model]["reported_usage_including_failed_stages"][stage]
                assert usage["missing_token_details"] == (
                    1 if (prefix == "Instruction" and model == "gpt-5.6-sol"
                          and stage == "compaction")
                    else 0)
                for key, suffix in (("inclusive_input_tokens", "Input"), ("output", "Output"),
                                    ("reported_nano_aiu", "NanoAiu")):
                    extension_numbers[short + label + suffix] = usage[key]
                if prefix == "Instruction" and usage["inclusive_input_tokens"] is None:
                    known = usage["known_disjoint_tokens"]
                    extension_numbers[short + label + "KnownInput"] = sum(
                        known[key] for key in ("input", "cache_read", "cache_write"))
                    extension_numbers[short + label + "KnownOutput"] = known["output"]
                    extension_numbers[short + label + "KnownNanoAiu"] = (
                        usage["known_reported_nano_aiu"])
                stages = [row["stages"][stage] for row in rows if stage in row["stages"]]
                assert all(item["seconds"] is not None for item in stages)
                extension_numbers[short + label + "Seconds"] = (
                    statistics.median(item["seconds"] for item in stages) if stages else None)
                extension_numbers[short + label + "TimingN"] = len(stages)
        if prefix == "Instruction":
            extension_numbers["FailedNativeSeconds"] = (
                extension_audit["failed_native_stage_wall_seconds"])
        if prefix in {"Instruction", "Sweep"}:
            extension_numbers["Sessions"] = extension_audit["distinct_sessions"]
            extension_numbers["NativeRequests"] = extension_audit["native_model_requests"]
            extension_numbers["Repairs"] = extension_audit["compaction_repairs"]
        if prefix == "Metadata":
            for model, short in MODELS.items():
                sensitivity = extension_audit["sensitivity_models"][model]
                extension_numbers[short + "WithoutPeriodPassed"] = (
                    sensitivity["exact_without_period_passed"])
                extension_numbers[short + "EitherReadingPassed"] = (
                    sensitivity["either_punctuation_reading_passed"])
        for key, value in extension_numbers.items():
            text = (r"\textit{incomplete}" if value is None else
                    f"{value:.1f}" if isinstance(value, float) else f"{value:,}")
            lines.append("\\newcommand{\\" + prefix + key + "}{"
                         + text.replace(",", "{,}") + "}")
    if "Palette" in extensions:
        palette_path = PILOT.parent / "reviewed-palette" / PALETTE / "colors.csv"
        palette_data = palette_reference(
            {"colors.csv": palette_path.read_bytes()})
        for suffix, key in (("Rows", "total_palettes"), ("Pairs", "total_pairs"),
                            ("FailingPairs", "failing_pairs")):
            lines.append("\\newcommand{\\Palette" + suffix + "}{" + str(palette_data[key]) + "}")
    for key, field in (
        ("Repositories", "repositories"), ("RepositoryVersions", "repository_commit_pairs"),
        ("PlannedExecutions", "planned_execution_trials"),
        ("UnmeasuredExecutions", "unmeasured_execution_trials"),
        ("PlannedCompactions", "planned_compaction_trials_before_retries"),
        ("ReviewedTasks", "reviewed_task_documents"),
        ("UnreviewedTasks", "documents_without_reviewed_task"),
        ("VerifiedExecutions", "verified_execution_trials"),
        ("QuarantinedExecutions", "quarantined_execution_trials"),
        ("QuarantinedTasks", "quarantined_task_documents"),
        ("FrozenReviewedTasks", "frozen_reviewed_task_documents"),
        ("TasksWithoutFrozenReview", "documents_without_frozen_reviewed_task"),
    ):
        value = f"{coverage[field]:,}".replace(",", "{,}")
        lines.append(r"\newcommand{\Cohort" + key + "}{" + value + "}")
    for key, field in (("BytePassed", "frozen_byte_rule_goals_achieved"),
                       ("TextPassed", "alternative_text_rule_goals_achieved"),
                       ("Sessions", "distinct_sessions"),
                       ("NativeRequests", "native_model_requests")):
        lines.append("\\newcommand{\\Layout" + key + "}{" + str(quarantined[2][field]) + "}")
    eligibility = json.loads((PILOT.parent / "reviewed-layout"
                              / "eligibility_accounting_20261123.json").read_bytes())
    assert eligibility["paid_attempts"] == len(eligibility["rows"]) == len(MODELS)
    assert {row["model"] for row in eligibility["rows"]} == set(MODELS)
    assert eligibility["new_model_calls_made"] == 0
    for row in eligibility["rows"]:
        for suffix, value in (("Input", row["inclusive_input_tokens"]),
                              ("Output", row["disjoint_tokens"]["output"]),
                              ("NanoAiu", row["reported_nano_aiu"]),
                              ("Seconds", row["seconds"])):
            value = f"{value:.1f}" if isinstance(value, float) else f"{value:,}"
            lines.append("\\newcommand{\\Layout" + MODELS[row["model"]] + "Probe" + suffix
                         + "}{" + value.replace(",", "{,}") + "}")
    (OUT / "real_skills_numbers.tex").write_text(
        "\n".join(lines) + "\n", encoding="ascii", newline="\n")


def draw(report, frozen):
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42})
    fig, axes = plt.subplots(1, 2, figsize=(7.1, 2.45), sharey=True)
    for ax, (source, (_, title)) in zip(axes, TASKS.items(), strict=True):
        ax.set_title(title, fontsize=9, fontweight="bold", pad=10)
        for row, model in enumerate(MODELS):
            trials = [t for t in report["trials"] if t["model"] == model and t["source"] == source]
            observed = {key: 0 for key, _, _ in OUTCOMES}
            for trial in trials:
                verdict = trial["stages"]["compaction"]["verdict"]
                outcome = trial["stages"]["execution"]["outcome"]
                assert verdict in {"ACHIEVABLE", "IMPOSSIBLE"}
                assert outcome in {"verified_goal_achieved",
                                   "verified_goal_not_achieved_with_runtime_evidence"}
                prefix = "blocked" if verdict == "IMPOSSIBLE" else "possible"
                key = prefix + ("_goal_achieved" if outcome == "verified_goal_achieved"
                                else "_goal_not_achieved")
                observed[key] += 1
            assert sum(observed.values()) == frozen["repeats"]
            left = 0
            for key, _, color in OUTCOMES:
                count = observed[key]
                if count:
                    ax.barh(row, count, left=left, height=0.48, color=color)
                    ax.text(left + count / 2, row, str(count), ha="center", va="center",
                            color="white" if key != "possible_goal_not_achieved" else "black",
                            fontweight="bold", fontsize=11)
                left += count
        ax.set_xlim(0, frozen["repeats"])
        ax.set_xticks(range(frozen["repeats"] + 1))
        ax.set_yticks(range(len(MODELS)), list(MODELS))
        ax.tick_params(axis="both", length=0)
        ax.set_xlabel("Fresh paired trials (counts, not percentages)", fontsize=7.5, labelpad=6)
        ax.set_axisbelow(True)
        ax.grid(axis="x", color="#E3E7EC", linewidth=0.6)
        for spine in ax.spines.values():
            spine.set_visible(False)
    axes[0].invert_yaxis()
    fig.legend(handles=[Patch(facecolor=c, label=name) for _, name, c in OUTCOMES],
               loc="lower center", ncol=2, frameon=False, fontsize=7.5,
               bbox_to_anchor=(0.5, -0.01))
    fig.subplots_adjust(left=0.17, right=0.98, top=0.80, bottom=0.37, wspace=0.12)
    for suffix in ("pdf", "png"):
        fig.savefig(OUT / f"fig_real_skills.{suffix}", dpi=240,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


def draw_cohort(coverage):
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch

    mpl.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8, "pdf.fonttype": 42})
    fig = plt.figure(figsize=(7.1, 3.2))
    fig.text(0.5, 0.96, "Full public-skill cohort: evidence coverage", ha="center",
             fontsize=12, fontweight="bold")
    cards = (
        ("Recovered public skill IDs", coverage["source_count"],
         f"{coverage['repositories']} repositories\n"
         f"{coverage['repository_commit_pairs']} repository/commit pairs", "#1F3A5F"),
        ("Sources with primary evidence", coverage["reviewed_task_documents"],
         f"{coverage['verified_execution_trials']:,} primary verified trials", "#227850"),
        ("Sources without primary evidence", coverage["documents_without_reviewed_task"],
         f"{coverage['unmeasured_execution_trials']:,} execution outcomes unverified", "#5F6B78"),
    )
    for x, (title, count, detail, color) in zip((0.025, 0.355, 0.685), cards, strict=True):
        fig.add_artist(FancyBboxPatch(
            (x, 0.61), 0.29, 0.27, boxstyle="round,pad=0.01", transform=fig.transFigure,
            facecolor="#F5F7FA", edgecolor=color, linewidth=0.8))
        fig.text(x + 0.145, 0.83, title, ha="center", fontsize=8)
        fig.text(x + 0.145, 0.735, f"{count:,}", ha="center", fontsize=23,
                 color=color, fontweight="bold")
        fig.text(x + 0.145, 0.645, detail, ha="center", va="center", fontsize=7)
    fig.text(
        0.5, 0.54,
        f"{len(coverage['models'])} models x {coverage['repeats_per_source_and_model']} "
        f"repeats per source: {coverage['planned_execution_trials']:,} planned executions",
        ha="center", fontsize=8)
    fig.text(0.5, 0.485,
             f"Plus {coverage['planned_compaction_trials_before_retries']:,} "
             "planned compaction/static-validation trials, before retries",
             ha="center", fontsize=7.5)
    if "quarantined_execution_trials" in coverage:
        fig.text(0.5, 0.445,
                 f"{coverage['quarantined_execution_trials']} completed trials quarantined; "
                 "interpretation sensitivities and all costs retained separately",
                 ha="center", fontsize=7)
    ax = fig.add_axes((0.025, 0.155, 0.95, 0.27))
    ax.axis("off")
    rows = []
    for model, result in coverage["models"].items():
        counts = result["observed_four_way_counts"]
        rows.append([
            model, counts["possible_goal_achieved"], counts["blocked_goal_achieved"],
            counts["possible_goal_not_achieved"], counts["blocked_goal_not_achieved"],
            counts["no_valid_prediction"], counts["unresolved_execution"],
            f"{result['unmeasured_executions']:,}", f"{result['planned_executions']:,}",
        ])
    table = ax.table(
        cellText=rows,
        colLabels=["Exact model", "Possible /\ngoal achieved", "Blocked /\ngoal achieved",
                   "Possible /\ngoal not\nachieved", "Blocked /\ngoal not\nachieved",
                   "Unknown /\nverified", "Unresolved\nattempts",
                   "No verified\noutcome", "Planned"],
        colWidths=[0.18, 0.11, 0.11, 0.11, 0.11, 0.105, 0.09, 0.11, 0.075],
        cellLoc="center", bbox=(0, 0, 1, 1))
    table.auto_set_font_size(False)
    table.set_fontsize(6.1)
    for (row, column), cell in table.get_celld().items():
        cell.set_edgecolor("#DCE1E8")
        cell.set_linewidth(0.5)
        if row == 0:
            cell.set_facecolor("#E8EDF4")
        elif column == 7:
            cell.set_facecolor("#F0F0F0")
    fig.text(0.5, 0.09, "Full-cohort accuracy, token cost and wall time: NOT YET MEASURED",
             ha="center", fontsize=8, fontweight="bold", color="#895A0D")
    fig.text(0.5, 0.035,
             "Unresolved attempts are included in no verified outcome; "
             "unmeasured is not failure or zero cost.",
             ha="center", fontsize=7)
    for suffix in ("pdf", "png"):
        fig.savefig(OUT / f"fig_real_skills_cohort.{suffix}", dpi=240,
                    bbox_inches="tight", pad_inches=0.06)
    plt.close(fig)


if __name__ == "__main__":
    report, frozen, audit = verified_report()
    extensions = {
        "Extension": verified_report(EXTENSION, {MUTATION_TASK}),
        "Palette": verified_report(PILOT.parent / "reviewed-palette",
                                   {"davila7__claude-code-templates__ui-ux-pro-max"}),
        "Property": verified_report(PILOT.parent / "reviewed-property", {PROPERTY}),
        "Batch": verified_report(PILOT.parent / "reviewed-batch", {BATCH}),
        "Sqlite": verified_report(PILOT.parent / "reviewed-sql", SQL_TASKS),
        "Notebook": verified_report(PILOT.parent / "reviewed-notebook", {NOTEBOOK}),
        "Caption": verified_report(PILOT.parent / "reviewed-captions", {CAPTION}),
        "Index": verified_report(PILOT.parent / "reviewed-index", {INDEX}),
        "Metadata": metadata_report(),
        "Symbolic": verified_report(PILOT.parent / "reviewed-symbolic", {SYMBOLIC}),
        "Instruction": instruction_report(),
        "Sweep": sweep_report(),
    }
    quarantined = quarantined_layout_report()
    coverage = full_cohort_report(report, frozen, audit, extensions, quarantined)
    write_numbers(report, frozen, audit, coverage, extensions, quarantined)
    draw(report, frozen)
    draw_cohort(coverage)
    print(f"Enumerated {coverage['source_count']} cohort documents; "
          f"{coverage['verified_execution_trials']} verified executions; "
          f"{coverage['unmeasured_execution_trials']} unmeasured execution trials. "
          "Rebuilt full-cohort Figure 3, pilot Figure 4, and LaTeX numbers.")
