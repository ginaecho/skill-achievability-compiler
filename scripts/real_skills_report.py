"""Sanitize pilot receipts and report explicit completion and outcome denominators."""
import argparse
import hashlib
import json
from pathlib import Path


def _native_files(folder: Path, name: str) -> list[Path]:
    paths = list(folder.glob(f"call-*/{name}"))
    if (folder / "session" / name).is_file():
        paths.append(folder / "session" / name)
    return paths


def _superseded(frozen: dict) -> dict:
    return {(s["model"], s["source"], s["repeat"], s["stage"]): s["rerun_folder"]
            for s in frozen.get("superseded_stages", [])}


def snapshot(pilot: Path, cache: Path, manifest: Path | None = None) -> Path:
    destination = pilot / "collected"
    frozen = json.loads((manifest or pilot / "frozen.json").read_text())
    superseded = _superseded(frozen)

    def retain(relative: Path, content: bytes) -> None:
        target = destination / relative
        if target.exists():
            if target.read_bytes() != content:
                raise ValueError(f"Collected artifact changed: {relative}")
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as handle:
            handle.write(content)

    for model in frozen["models"]:
        for case in frozen["cases"]:
            for repeat in range(1, frozen["repeats"] + 1):
                root = Path(frozen.get("trial_namespace", "pilot-trials")) / model / case["id"] / f"r{repeat}"
                for stage in ("compaction", "execution"):
                    relative = root / superseded.get((model, case["id"], repeat, stage), stage)
                    folder = cache / relative
                    usage_paths = _native_files(folder, "usage.json")
                    for receipt in _native_files(folder, "receipt.json"):
                        if not receipt.with_name("usage.json").is_file():
                            retain(relative / receipt.parent.relative_to(folder)
                                   / "usage_unavailable.json",
                                   b'{"reason":"native_session_without_usage_receipt"}\n')
                    if (not (folder / "result.json").exists()
                            and not (folder / "failure.json").exists() and not usage_paths):
                        continue
                    for path in folder.glob("*"):
                        if path.is_file() and (path.name in {
                                "result.json", "failure.json", "verification.json",
                                "filesystem_snapshot.json",
                                "actual.py", "actual.json", "actual.sql", "actual.ipynb", "actual.md", "actual.html",
                                "actual.csv", "actual.sh", "actual.txt", "reply.txt",
                                "tools.jsonl", "repair_rejected.json",
                                "recovery.json"}
                                or path.name.startswith("reply-") and path.suffix == ".txt"):
                            retain(relative / path.name, path.read_bytes())
                    for path in usage_paths:
                        raw = path.read_bytes()
                        usage = json.loads(raw)
                        clean = {k: usage[k] for k in (
                            "tokenDetails", "totalNanoAiu", "totalPremiumRequestCost",
                            "totalApiDurationMs") if k in usage}
                        clean["original_sha256"] = hashlib.sha256(raw).hexdigest()
                        retain(relative / path.relative_to(folder),
                               (json.dumps(clean, indent=2) + "\n").encode())
    return destination


def collect(pilot: Path, cache: Path, manifest: Path | None = None) -> dict:
    frozen = json.loads((manifest or pilot / "frozen.json").read_text())
    superseded = _superseded(frozen)
    report = {
        "scope": frozen["scope"], "representative_full_study_results": False,
        "public_input_tasks": len(frozen["cases"]), "models": {},
        "pending_stages": [], "failed_stages": [], "recovered_stages": [], "trials": [],
    }
    for model in frozen["models"]:
        counts = {
            "blocked_goal_not_achieved": 0, "blocked_goal_achieved": 0,
            "possible_goal_achieved": 0, "possible_goal_not_achieved": 0,
            "no_valid_prediction": 0, "unresolved_execution": 0,
        }
        measured = {}
        timings = {
            stage: {"reported_trials": 0, "missing_trials": 0, "known_total_seconds": 0.0}
            for stage in ("compaction", "execution")
        }
        verified = correct = finished = 0
        for case in frozen["cases"]:
            for repeat in range(1, frozen["repeats"] + 1):
                root = cache / frozen.get("trial_namespace", "pilot-trials") / model / case["id"] / f"r{repeat}"
                trial = {"model": model, "source": case["id"], "repeat": repeat}
                stages = {}
                for stage in ("compaction", "execution"):
                    folder = root / superseded.get((model, case["id"], repeat, stage), stage)
                    result_path = folder / "result.json"
                    identity = {**trial, "stage": stage}
                    if result_path.exists():
                        result = json.loads(result_path.read_text())
                        if any(result[key] != value for key, value in identity.items()):
                            raise ValueError(f"Trial identity mismatch at {result_path}")
                        stages[stage] = result
                        finished += 1
                        if result.get("recovered_from_actual_tool_output"):
                            report["recovered_stages"].append(identity)
                        seconds = result.get("seconds")
                        if isinstance(seconds, (int, float)) and seconds >= 0:
                            timings[stage]["reported_trials"] += 1
                            timings[stage]["known_total_seconds"] += seconds
                        else:
                            timings[stage]["missing_trials"] += 1
                    elif (folder / "failure.json").exists():
                        report["failed_stages"].append(identity)
                    else:
                        report["pending_stages"].append(identity)
                    usage_paths = _native_files(folder, "usage.json")
                    unavailable = [
                        path for path in (_native_files(folder, "receipt.json")
                                          + _native_files(folder, "usage_unavailable.json"))
                        if not path.with_name("usage.json").is_file()
                    ]
                    result_usage = stages.get(stage, {}).get("usage")
                    expected_receipts = (result_usage.get("usage_files")
                                         if isinstance(result_usage, dict) else None)
                    missing_receipts = (
                        bool(unavailable) or (result_path.exists() and not usage_paths)
                        or (expected_receipts is not None
                            and expected_receipts != len(usage_paths))
                        or stages.get(stage, {}).get("accounting_complete") is False)
                    account = measured.setdefault(stage, {
                        "input": 0, "cache_read": 0, "cache_write": 0, "output": 0,
                        "reported_nano_aiu": 0, "usage_receipts": 0, "missing_token_details": 0,
                    })
                    # Interrupted multi-call stages may have receipts for only completed calls.
                    if (missing_receipts
                            or (not result_path.exists()
                                and ((folder / "failure.json").exists() or usage_paths))):
                        account.setdefault("unreported_stages", []).append({
                            **identity, "reason": ("missing_native_usage_receipts"
                                                  if missing_receipts else
                                                  "stage_not_completed"),
                        })
                    for path in usage_paths:
                        usage = json.loads(path.read_text())
                        account["usage_receipts"] += 1
                        if "tokenDetails" not in usage:
                            account["missing_token_details"] += 1
                        else:
                            for key in ("input", "cache_read", "cache_write", "output"):
                                account[key] += usage["tokenDetails"][key]["tokenCount"]
                        account["reported_nano_aiu"] += usage["totalNanoAiu"]
                if stages:
                    trial["stages"] = stages
                    report["trials"].append(trial)
                execution = stages.get("execution", {})
                outcome = execution.get("outcome")
                if outcome not in {
                        "verified_goal_achieved", "verified_goal_not_achieved_with_runtime_evidence"}:
                    if execution:
                        counts["unresolved_execution"] += 1
                    continue
                verified += 1
                passed = outcome == "verified_goal_achieved"
                verdict = stages.get("compaction", {}).get("verdict")
                if verdict == "IMPOSSIBLE":
                    counts["blocked_goal_achieved" if passed else "blocked_goal_not_achieved"] += 1
                    correct += not passed
                elif verdict == "ACHIEVABLE":
                    counts["possible_goal_achieved" if passed else "possible_goal_not_achieved"] += 1
                    correct += passed
                else:
                    counts["no_valid_prediction"] += 1
        for account in measured.values():
            account["inclusive_input_tokens"] = (
                account["input"] + account["cache_read"] + account["cache_write"])
            if account["missing_token_details"] or account.get("unreported_stages"):
                account["known_disjoint_tokens"] = {
                    key: account[key] for key in ("input", "cache_read", "cache_write", "output")
                }
                for key in account["known_disjoint_tokens"]:
                    account[key] = None
                account["inclusive_input_tokens"] = None
            if account.get("unreported_stages"):
                account["known_reported_nano_aiu"] = account["reported_nano_aiu"]
                account["reported_nano_aiu"] = None
        report["models"][model] = {
            "planned_executions": len(frozen["cases"]) * frozen["repeats"],
            "finished_stages": finished, "verified_executions": verified,
            "diagnostic_prediction_agreement": correct / verified if verified else None,
            "four_way_counts": counts, "reported_usage_including_failed_stages": measured,
            "stage_timing_coverage": timings,
        }
    incomplete = (report["pending_stages"] or report["failed_stages"] or any(
        model["four_way_counts"]["unresolved_execution"]
        or any(account["inclusive_input_tokens"] is None
               for account in model["reported_usage_including_failed_stages"].values())
        for model in report["models"].values()
    ))
    report["status"] = "incomplete_pilot" if incomplete else "complete_pilot"
    return report


def cohort_coverage(cohort: dict, frozen: dict, report: dict) -> dict:
    sources = {case["id"]: case for case in cohort["cases"]}
    if not sources or len(sources) != len(cohort["cases"]):
        raise ValueError("Empty cohort or duplicate source identifiers")
    reviewed = {case["id"]: case for case in frozen["cases"]}
    if len(reviewed) != len(frozen["cases"]):
        raise ValueError("Duplicate reviewed task identifiers")
    for source, case in reviewed.items():
        if source not in sources or any(
                case["skill_source"][key] != sources[source][key]
                for key in ("repository", "commit", "path_in_repo", "sha256")):
            raise ValueError(f"Reviewed task does not match the pinned cohort source: {source}")
    models, repeats = frozen["models"], frozen["repeats"]
    if not models or len(set(models)) != len(models) or repeats < 1:
        raise ValueError("Invalid model or repeat denominator")
    if set(models) != set(report["models"]):
        raise ValueError("Model identities differ between the manifest and report")
    seen = set()
    verified = {source: 0 for source in sources}
    for trial in report["trials"]:
        identity = (trial["source"], trial["model"], trial["repeat"])
        if (identity in seen or trial["source"] not in reviewed or trial["model"] not in models
                or trial["repeat"] not in range(1, repeats + 1)):
            raise ValueError(f"Invalid or duplicate trial identity: {identity}")
        seen.add(identity)
        if trial["stages"].get("execution", {}).get("outcome") in {
                "verified_goal_achieved", "verified_goal_not_achieved_with_runtime_evidence"}:
            verified[trial["source"]] += 1
    per_source = len(models) * repeats
    per_model = len(sources) * repeats
    model_coverage = {}
    for model in models:
        measured = report["models"][model]
        completed = measured["verified_executions"]
        counts = measured["four_way_counts"]
        decided = sum(counts[key] for key in (
            "possible_goal_achieved", "possible_goal_not_achieved",
            "blocked_goal_achieved", "blocked_goal_not_achieved", "no_valid_prediction"))
        actual = sum(t["model"] == model and t["stages"].get("execution", {}).get("outcome")
                     in {"verified_goal_achieved",
                         "verified_goal_not_achieved_with_runtime_evidence"}
                     for t in report["trials"])
        if completed != decided or completed != actual or completed > per_model:
            raise ValueError(f"Execution coverage does not reconcile for {model}")
        model_coverage[model] = {
            "planned_executions": per_model, "verified_executions": completed,
            "unmeasured_executions": per_model - completed,
            "observed_four_way_counts": counts,
        }
    completed = sum(verified.values())
    planned = len(sources) * per_source
    return {
        "status": "incomplete_benchmark" if completed != planned else "complete_benchmark",
        "source_count": len(sources),
        "repositories": len({case["repository"].casefold() for case in sources.values()}),
        "repository_commit_pairs": len({
            (case["repository"].casefold(), case["commit"]) for case in sources.values()}),
        "repository_spellings": len({case["repository"] for case in sources.values()}),
        "repository_commit_pair_spellings": len({
            (case["repository"], case["commit"]) for case in sources.values()}),
        "reviewed_task_documents": len(reviewed),
        "documents_without_reviewed_task": len(sources) - len(reviewed),
        "repeats_per_source_and_model": repeats,
        "planned_compaction_trials_before_retries": planned,
        "recorded_compaction_trials": sum("compaction" in t["stages"] for t in report["trials"]),
        "planned_execution_trials": planned, "verified_execution_trials": completed,
        "unmeasured_execution_trials": planned - completed,
        "models": model_coverage,
        "full_cohort_accuracy": None, "full_cohort_tokens": None,
        "full_cohort_wall_time_seconds": None,
        "documents": [
            {**case, "reviewed_task": source in reviewed,
             "planned_executions": per_source, "verified_executions": verified[source],
             "unmeasured_executions": per_source - verified[source]}
            for source, case in sources.items()
        ],
    }


def combined_cohort_coverage(cohort: dict, observations: list[tuple[dict, dict]]) -> dict:
    """Reconcile disjoint frozen source sets without pooling their cost measurements."""
    if not observations:
        raise ValueError("Coverage requires frozen observed source sets")
    first = observations[0][0]
    frozen = {"models": first["models"], "repeats": first["repeats"], "cases": []}
    report = {"trials": [], "models": {}}
    for manifest, observed in observations:
        if (manifest["models"] != frozen["models"] or manifest["repeats"] != frozen["repeats"]
                or set(observed["models"]) != set(frozen["models"])):
            raise ValueError("Coverage sources use different models or repeat counts")
        cohort_coverage(cohort, manifest, observed)
        frozen["cases"].extend(manifest["cases"])
        report["trials"].extend(observed["trials"])
        for model, result in observed["models"].items():
            total = report["models"].setdefault(
                model, {"verified_executions": 0, "four_way_counts": {}})
            total["verified_executions"] += result["verified_executions"]
            for key, value in result["four_way_counts"].items():
                counts = total["four_way_counts"]
                counts[key] = counts.get(key, 0) + value
    return cohort_coverage(cohort, frozen, report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    local = snapshot(args.pilot, args.cache)
    result = collect(args.pilot, local)
    (args.pilot / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "trials"}, indent=2))
