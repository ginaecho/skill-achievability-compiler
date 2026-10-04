"""Score the ext test (runs/20260927_ext/PLAN.md): P2g vs P2g + library veto.

Every ext skill was executed blindly; labels are in runs/20260927_ext/execution/.

  python scripts/benchmark_ce_runtime.py score runs/20260927_ext/ext_ce_rt
  python scripts/benchmark_ce_runtime.py score runs/20260927_ext/ext_ce_rt --veto core --tag _vcore
  python scripts/benchmark_ce_runtime.py score runs/20260927_ext/ext_ce_rt --veto any --tag _vany
  python scripts/benchmark_ce_runtime.py score runs/20260927_ext/ext_ce_rt --no-repair --tag _p1
  python scripts/compare_ext.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from scripts.benchmark_ce import mcnemar_exact, write_json  # noqa: E402
from scripts.compare_heldout import label, metrics  # noqa: E402

RUN = ROOT / "runs" / "20260927_ext"
OUT = RUN / "ext_ce_rt"
PRIMARY, BASE = "P2g + core veto", "P2g"
VARIANTS = {
    "P1 (no repair)": "results_p1.json",
    "P2g": "results.json",
    "P2g + core veto": "results_vcore.json",
    "P2g + any veto": "results_vany.json",
    "core veto alone": "results_vcore.json",
}


def load_labels() -> dict:
    return {p.stem: json.loads(p.read_text()) for p in sorted((RUN / "execution").glob("*.json"))}


def verdicts_of(name: str, rows: list) -> dict:
    if name == "core veto alone":
        return {r["case"]: "IMPOSSIBLE" if r.get("veto") else "ACHIEVABLE" for r in rows}
    return {r["case"]: (r.get("verdict") if r["valid"] or r.get("reason") == "LIBRARY_VETO"
                        else "INVALID") for r in rows}


def paired(a: dict, b: dict, cases, decided) -> dict:
    """a better / worse than b on decided cases (L2)."""
    def right(v, c):
        return (v[c] == "IMPOSSIBLE") == (decided[c] == "IMPOSSIBLE")
    better = sum(right(a, c) and not right(b, c) for c in cases)
    worse = sum(right(b, c) and not right(a, c) for c in cases)
    return {"better": better, "worse": worse, "mcnemar_p": mcnemar_exact(better, worse)}


def main() -> None:
    labels = load_labels()
    frozen = json.loads((OUT / "frozen.json").read_text())
    corpus = {c["id"]: c["corpus"] for c in frozen["cases"]}
    missing = sorted(set(corpus) - set(labels))
    if missing:
        raise SystemExit(f"{len(missing)} skills not executed yet: {missing[:5]} ...")
    table: dict = {"labels": {s: {k: sum(label(e, s) == k for e in labels.values())
                                  for k in ("ACHIEVABLE", "IMPOSSIBLE", "INCONCLUSIVE")}
                              for s in ("L1", "L2")}}
    V, rows_by = {}, {}
    for name, fname in VARIANTS.items():
        rows = json.loads((OUT / fname).read_text())
        rows_by[name] = {r["case"]: r for r in rows}
        V[name] = verdicts_of(name, rows)
        table[name] = {s: metrics(V[name], labels, s) for s in ("L1", "L2")}
        for part in ("ce_sources", "ce_sources_ext"):
            sub = {c: v for c, v in V[name].items() if corpus[c] == part}
            table[name][f"L2_{part}"] = metrics(sub, labels, "L2")
    decided = {c: label(e, "L2") for c, e in labels.items()}
    decided = {c: l for c, l in decided.items() if l != "INCONCLUSIVE"}
    for name in VARIANTS:
        if name != BASE:
            table[name]["accuracy_vs_P2g"] = paired(V[name], V[BASE], decided, decided)

    # pre-registered criteria
    base, prim = table[BASE]["L2"], table[PRIMARY]["L2"]
    pos = int(base["recall"].split("/")[1])
    rec_b, rec_p = base["tp"] / pos if pos else 0, prim["tp"] / pos if pos else 0
    flips = [c for c in V[PRIMARY] if V[PRIMARY][c] == "IMPOSSIBLE" and V[BASE][c] != "IMPOSSIBLE"]
    flip_lab = {c: label(labels[c], "L2") for c in flips}
    f_tp = sum(v == "IMPOSSIBLE" for v in flip_lab.values())
    f_fp = sum(v == "ACHIEVABLE" for v in flip_lab.values())
    acc = lambda m: int(m["accuracy_decided"].split("/")[0])  # noqa: E731
    missed_by_p2g = base["recall"].split("/")
    table["criteria"] = {
        "1_recall_gain_>=10pp": {
            "P2g_recall": base["recall"], "primary_recall": prim["recall"],
            "gain_pp": round(100 * (rec_p - rec_b), 1),
            "testable": int(missed_by_p2g[1]) - int(missed_by_p2g[0]) >= 4,
            "met": rec_p - rec_b >= 0.10},
        "2_added_false_rejections": {
            "veto_flips": len(flips), "flip_confirmed": f_tp, "flip_false": f_fp,
            "flip_precision_decided": f"{f_tp}/{f_tp + f_fp}",
            "met": f_fp <= 2 and (f_tp + f_fp == 0 or f_tp / (f_tp + f_fp) >= 0.75)},
        "3_net_gain": {"P2g": base["accuracy_decided"], "primary": prim["accuracy_decided"],
                       "met": acc(prim) >= acc(base)},
    }
    table["vetoes"] = {c: {"veto": rows_by[PRIMARY][c].get("veto"),
                           "P2g": V[BASE][c], "label": labels[c]["outcome"],
                           "blocker_kind": labels[c]["blocker_kind"]}
                       for c in V[PRIMARY] if rows_by[PRIMARY][c].get("veto")}
    table["any_vetoes"] = {c: {"veto": rows_by["P2g + any veto"][c].get("veto"),
                               "label": labels[c]["outcome"],
                               "blocker_kind": labels[c]["blocker_kind"]}
                           for c in V[PRIMARY] if rows_by["P2g + any veto"][c].get("veto")}
    table["per_case"] = {c: {"corpus": corpus[c], "label": labels[c]["outcome"],
                             "blocker_kind": labels[c]["blocker_kind"],
                             **{n: V[n][c] for n in VARIANTS}} for c in sorted(labels)}
    write_json(RUN / "comparison.json", table)
    print(json.dumps(table["labels"]))
    for name in VARIANTS:
        t = table[name]["L2"]
        print(f"{name:18} rej={t['rejections']:3} prec={t['precision']:>6} rec={t['recall']:>6} "
              f"FR={t['false_rejection_rate']:>6} acc={t['accuracy_decided']:>7}  "
              f"orig acc={table[name]['L2_ce_sources']['accuracy_decided']:>6} "
              f"ext acc={table[name]['L2_ce_sources_ext']['accuracy_decided']:>6}  "
              + str(table[name].get("accuracy_vs_P2g", "")))
    print(json.dumps(table["criteria"], indent=1))


if __name__ == "__main__":
    main()
