"""Compare methods on the held-out and fresh sets (docs/P2G_RUNTIME_BINDING.md).

Every held-out skill was executed blindly, so each method's IMPOSSIBLE
verdicts can be scored for precision AND recall against the same labels.

  python scripts/compare_heldout.py            # prints and writes the table
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.benchmark_ce import mcnemar_exact, wilson, write_json  # noqa: E402
from scripts.benchmark_ce_runtime import L2_CONFIRMING  # noqa: E402

RUNS = ROOT / "runs"
LABELS = RUNS / "20260926_heldout_execution.json"
# variant -> (run directory, results file)
VARIANTS = {
    "json (original)": ("20260926_heldout_json", "results.json"),
    "P1 ce_rt": ("20260926_heldout_ce_rt", "results_p1.json"),
    "P2g ce_rt+repair+guard": ("20260926_heldout_ce_rt", "results.json"),
    "P2g + pruning": ("20260926_heldout_ce_rt", "results_prune.json"),
}


def label(entry: dict, scheme: str) -> str:
    if entry["outcome"] == "achieved":
        return "ACHIEVABLE"
    kinds = {"missing_tool_in_runtime"} if scheme == "L1" else L2_CONFIRMING
    return "IMPOSSIBLE" if entry["blocker_kind"] in kinds else "INCONCLUSIVE"


def metrics(verdicts: dict, labels: dict, scheme: str) -> dict:
    lab = {c: label(labels[c], scheme) for c in verdicts}
    rej = {c for c, v in verdicts.items() if v == "IMPOSSIBLE"}
    tp = sum(lab[c] == "IMPOSSIBLE" for c in rej)
    fp = sum(lab[c] == "ACHIEVABLE" for c in rej)
    pos = [c for c in verdicts if lab[c] == "IMPOSSIBLE"]
    neg = [c for c in verdicts if lab[c] == "ACHIEVABLE"]
    tn = sum(c not in rej for c in neg)
    decided = len(pos) + len(neg)
    return {"rejections": len(rej), "tp": tp, "fp": fp,
            "inconclusive_rejections": len(rej) - tp - fp,
            "precision": f"{tp}/{tp + fp}", "precision_ci95": wilson(tp, tp + fp),
            "recall": f"{tp}/{len(pos)}", "recall_ci95": wilson(tp, len(pos)),
            "false_rejection_rate": f"{fp}/{len(neg)}",
            "accuracy_decided": f"{tp + tn}/{decided}",
            "accuracy_ci95": wilson(tp + tn, decided)}


FRESH_LABELS = RUNS / "20260926_tpl" / "execution.json"
FRESH_VARIANTS = {
    "json (original)": ("20260926_tpl/fresh_json", "results.json"),
    "P1 ce_rt": ("20260926_tpl/fresh_ce_rt", "results_p1.json"),
    "P2g ce_rt+repair+guard": ("20260926_tpl/fresh_ce_rt", "results.json"),
    "TPL (no repair)": ("20260926_tpl/fresh_ce_tpl", "results_norepair.json"),
    "TPL, binder without library": ("20260926_tpl/fresh_ce_tpl", "results_nolib.json"),
    "TPL, no pruning": ("20260926_tpl/fresh_ce_tpl", "results_noprune.json"),
    "TPL": ("20260926_tpl/fresh_ce_tpl", "results.json"),
}


def main() -> None:
    global LABELS, VARIANTS
    fresh = "--fresh" in sys.argv
    if fresh:
        LABELS, VARIANTS = FRESH_LABELS, FRESH_VARIANTS
    labels = json.loads(LABELS.read_text())
    table: dict = {"labels": {s: {k: sum(label(e, s) == k for e in labels.values())
                                  for k in ("ACHIEVABLE", "IMPOSSIBLE", "INCONCLUSIVE")}
                              for s in ("L1", "L2")}}
    verdicts = {}
    for name, (run, fname) in VARIANTS.items():
        rows = json.loads((RUNS / run / fname).read_text())
        verdicts[name] = {r["case"]: (r.get("verdict") if r["valid"] else "INVALID")
                          for r in rows}
        missing = set(labels) - set(verdicts[name])
        if missing:
            raise ValueError(f"{name}: no verdict for {sorted(missing)}")
        unlabelled = sorted(set(verdicts[name]) - set(labels))
        verdicts[name] = {c: v for c, v in verdicts[name].items() if c in labels}
        table.setdefault("unlabelled", unlabelled)
        table[name] = {"valid": sum(r["valid"] for r in rows),
                       **{s: metrics(verdicts[name], labels, s) for s in ("L1", "L2")}}
    achieved = [c for c, e in labels.items() if e["outcome"] == "achieved"]
    for base in ("json (original)", "P2g ce_rt+repair+guard"):
        for name in VARIANTS:
            if name == base:
                continue
            b = sum(verdicts[base][c] == "IMPOSSIBLE" and verdicts[name][c] != "IMPOSSIBLE"
                    for c in achieved)
            w = sum(verdicts[base][c] != "IMPOSSIBLE" and verdicts[name][c] == "IMPOSSIBLE"
                    for c in achieved)
            table[name].setdefault("false_rejections_vs", {})[base] = {
                "fixed": b, "introduced": w, "mcnemar_p": mcnemar_exact(b, w)}
    # paired decided-accuracy test (L2 labels): correct = rejected a confirmed
    # impossible, or did not reject an achieved skill
    decided = {c: label(labels[c], "L2") for c in labels}
    decided = {c: l for c, l in decided.items() if l != "INCONCLUSIVE"}

    def right(name, c):
        return (verdicts[name][c] == "IMPOSSIBLE") == (decided[c] == "IMPOSSIBLE")
    for base in ("json (original)", "P2g ce_rt+repair+guard"):
        for name in VARIANTS:
            if name == base:
                continue
            b = sum(right(name, c) and not right(base, c) for c in decided)
            w = sum(right(base, c) and not right(name, c) for c in decided)
            table[name].setdefault("accuracy_vs", {})[base] = {
                "better": b, "worse": w, "mcnemar_p": mcnemar_exact(b, w)}
    table["per_case"] = {c: {"label": labels[c]["outcome"],
                             "blocker_kind": labels[c]["blocker_kind"],
                             **{n: verdicts[n][c] for n in VARIANTS}}
                         for c in sorted(labels)}
    write_json(RUNS / ("20260926_tpl/comparison.json" if fresh else
                       "20260926_heldout_comparison.json"), table)
    print(json.dumps(table["labels"]))
    for name in VARIANTS:
        t = table[name]
        print(f"{name:24} valid={t['valid']:2}  L2: rej={t['L2']['rejections']:2} "
              f"prec={t['L2']['precision']:>5} rec={t['L2']['recall']:>5} "
              f"FR={t['L2']['false_rejection_rate']:>5} acc={t['L2']['accuracy_decided']:>5}"
              f"  | L1 prec={t['L1']['precision']:>5} rec={t['L1']['recall']:>4}"
              + ("" if name.startswith("json") else
                 f"  | acc vs json {t['accuracy_vs']['json (original)']}"))


if __name__ == "__main__":
    main()
