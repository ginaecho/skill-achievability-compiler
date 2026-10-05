"""Run every Execution Atlas catalog entry through the current local pipeline."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

import refutation_metrics
from intent_catalog import TOPIC_SUITE, load_catalog
from skillc import compile_markdown, load_profile
from skillc.cli import check_compiled
from skillc.frontend.contracts import bind_environment
from skillc.pack import PackError


def compact_entry(entry: dict, llm_model: str | None = None):
    """Return (pack, deterministic CompileResult or None for LLM compaction)."""
    if llm_model:
        from skillc.frontend.llm import compact

        pack = compact(entry["content"], model=llm_model, provider="azure-openai",
                       vocabulary=entry.get("environment_manifest"))
        return pack, None
    profile = load_profile("none").with_tools(entry["environment_grants"])
    compiled = compile_markdown(entry["content"], profile)
    return compiled.pack, compiled


def try_compact(entry: dict, llm_model: str | None = None):
    """compact_entry, with a frontend failure returned instead of raised."""
    try:
        return compact_entry(entry, llm_model)
    except (PackError, ValueError, RuntimeError) as error:
        return error


def evaluate_entry(entry: dict, llm_model: str | None = None, compaction=None) -> dict:
    """Bind and check one entry; `compaction` is a precomputed try_compact result."""
    row = {
        "id": entry["id"],
        "base_id": entry["base_id"],
        "name": entry["name"],
        "suite": entry["suite"],
        "input_type": entry["input_type"],
        "form_provenance": entry["form_provenance"],
        "source_path": entry["source_path"],
        "expected": entry.get("expected"),
    }
    compaction = try_compact(entry, llm_model) if compaction is None else compaction
    try:
        if isinstance(compaction, Exception):
            raise compaction
        pack, compiled = compaction
        binding = bind_environment(pack, entry["environment_grants"],
                                   entry.get("environment_manifest"))
        verdict = check_compiled(
            binding.pack, compiled,
            vocabulary_states=(entry.get("environment_manifest") or {}).get("states"),
            source_text=entry["content"])
    except (PackError, ValueError, RuntimeError) as error:
        return {**row, "observed": "ERROR", "reason": f"{type(error).__name__}: {error}"[:300],
                "frontier": [], "matches_expected": None, "comparison": "error"}
    return {
        **row,
        "observed": verdict.label,
        "reason": verdict.reason,
        "frontier": list(verdict.frontier),
        "matches_expected": None if row["expected"] is None else verdict.label == row["expected"],
        "comparison": _comparison(entry, verdict.label),
        "goal_source": compiled.goal_source if compiled else "llm",
        "required": list(binding.required),
        "granted": list(binding.granted),
        "unavailable": list(binding.unavailable),
        "contracts_applied": list(binding.contracts_applied),
        "unaligned": list(binding.unaligned),
        "compacted_pack": pack,
        "bound_pack": binding.pack,
    }


def _comparison(entry: dict, observed: str) -> str:
    expected = entry.get("expected")
    if expected is None:
        return "unscored"
    if observed == expected:
        return "match"
    if entry["category"] == "SPURIOUS" and observed == "ACHIEVABLE":
        return "expected_incompleteness"
    if observed == "UNKNOWN":
        return "frontend_abstention"
    return "mismatch"


def run_catalog(data_root: Path | None = None, llm_model: str | None = None,
                workers: int = 6, reuse: dict | None = None) -> dict:
    catalog = load_catalog(REPO_ROOT, data_root)
    entries = [entry for entry in catalog["entries"] if entry["suite"] == TOPIC_SUITE]
    if reuse is not None:
        # Re-check stored compactions: isolates binding/checker changes from LLM variance.
        compactions = [
            (reuse[entry["id"]], None) if entry["id"] in reuse
            else ValueError("no stored compaction for this entry")
            for entry in entries
        ]
    elif llm_model:
        from concurrent.futures import ThreadPoolExecutor

        # Only the network-bound compaction is parallel: z3 is not thread-safe.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            compactions = list(pool.map(lambda entry: try_compact(entry, llm_model), entries))
    else:
        compactions = [None] * len(entries)
    rows = [evaluate_entry(entry, llm_model, compaction)
            for entry, compaction in zip(entries, compactions)]
    scored = [row for row in rows if row["matches_expected"] is not None]
    observed_by_base: dict[str, set[str]] = {}
    for row in rows:
        observed_by_base.setdefault(row["base_id"], set()).add(row["observed"])
    inconsistent = sorted(
        base_id for base_id, verdicts in observed_by_base.items()
        if len(verdicts) > 1
    )
    return {
        "schema": "skillc.catalog-benchmark/1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "catalog": catalog["branch"],
        "compaction": f"llm:{llm_model}" if llm_model else "deterministic",
        "total": len(rows),
        "by_input_type": dict(sorted(Counter(
            row["input_type"] for row in rows
        ).items())),
        "by_observed_verdict": dict(sorted(Counter(
            row["observed"] for row in rows
        ).items())),
        "by_comparison": dict(sorted(Counter(
            row["comparison"] for row in rows
        ).items())),
        "scored": len(scored),
        "matches_expected": sum(row["matches_expected"] is True for row in scored),
        "cross_form_inconsistencies": inconsistent,
        "confusion": {
            scope: refutation_metrics.confusion(
                rows if scope == "all" else [r for r in rows if r["input_type"] == scope])
            for scope in ("all", "skill", "agent", "prompt")
        },
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-root", type=Path)
    parser.add_argument("--llm", metavar="DEPLOYMENT",
                        help="compact with this Azure OpenAI deployment instead of the "
                             "deterministic frontend (needs AZURE_OPENAI_ENDPOINT)")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--reuse", type=Path,
                        help="re-check the compacted packs stored in an earlier LLM "
                             "results file instead of calling the LLM again")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    reuse = None
    if args.reuse:
        stored = json.loads(args.reuse.read_text(encoding="utf-8"))
        reuse = {row["id"]: row["compacted_pack"] for row in stored["rows"]
                 if "compacted_pack" in row}
        args.llm = args.llm or stored.get("compaction", "").removeprefix("llm:")
    suffix = "-llm" if args.llm else ""
    output = args.output or Path(__file__).with_name(f"benchmark-results{suffix}.json")
    report = run_catalog(args.catalog_root, args.llm, args.workers, reuse)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        f"{report['total']} cases: {report['by_input_type']}; "
        f"verdicts: {report['by_observed_verdict']}; "
        f"expected matches: {report['matches_expected']}/{report['scored']}; "
        f"cross-form inconsistencies: "
        f"{len(report['cross_form_inconsistencies'])}"
    )
    for scope, m in report["confusion"].items():
        fpr, precision = m["false_positive_rate"], m["precision"]
        recall = m["recall_all_labelled_impossible"]
        print(f"  {scope:6} n={m['labelled']:3} TP={m['tp']:3} FP={m['fp']:2} FN={m['fn']:3} "
              f"TN={m['tn']:3} UNK={m['unknown_on_achievable'] + m['unknown_on_impossible']:2} "
              f"FPR={fpr['value']} {fpr['ci95']} precision={precision['value']} "
              f"recall(all)={recall['value']} {recall['ci95']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
