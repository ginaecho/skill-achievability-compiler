"""Score the diversity test (runs/20260928_div/PLAN.md) against blind execution labels.

  python scripts/score_div.py RUN_DIR [RUN_DIR ...]      e.g. div_ce_rt div_ce_idx

Each RUN_DIR must already be scored by `benchmark_ce_runtime.py score` (results.json).
Labels (L2): achieved -> ACHIEVABLE; blocker missing_tool_in_runtime,
needs_credentials_or_account or forbidden_by_safety_rules -> CONFIRMED (in
offline-workstation, network_or_service_unavailable too); otherwise INCONCLUSIVE.
Sensitivity: `strict` treats achieved reports that runs/20260928_div/adjudication.json
marks "simulated" as INCONCLUSIVE; `no_violations` drops protocol_violations.txt cases.
Writes RUN_DIR/div_metrics.json and, for two runs, DIV/comparison.json.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.benchmark_ce import mcnemar_exact, wilson  # noqa: E402
from scripts.benchmark_ce_runtime import L2_CONFIRMING, preq_batch  # noqa: E402

DIV = ROOT / "runs" / "20260928_div"


def labels(scheme: str = "L2") -> dict:
    adj = {}
    if (DIV / "adjudication.json").exists():
        adj = json.loads((DIV / "adjudication.json").read_text())
    out = {}
    for f in sorted((DIV / "execution").glob("*.json")):
        d = json.loads(f.read_text())
        cid, rt = f.stem, f.stem.split("@")[1]
        bk = d.get("blocker_kind")
        if d.get("outcome") == "achieved":
            lab = "ACHIEVABLE"
            if scheme == "strict" and adj.get(cid, {}).get("verdict") == "simulated":
                lab = "INCONCLUSIVE"
        elif bk in L2_CONFIRMING or (rt == "offline-workstation"
                                     and bk == "network_or_service_unavailable"):
            lab = "CONFIRMED"
        else:
            lab = "INCONCLUSIVE"
        out[cid] = {"label": lab, "blocker_kind": bk}
    return out


def violations() -> set[str]:
    p = DIV / "protocol_violations.txt"
    return {ln.split()[0] for ln in p.read_text().splitlines() if ln.strip()} if p.exists() else set()


def _rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "value": round(k / n, 4) if n else None, "ci95": wilson(k, n)}


def metrics(rows: list[dict], lab: dict) -> dict:
    tp = fn = fp = tn = inc = 0
    for r in rows:
        l = lab.get(r["case"], {}).get("label", "UNEXECUTED")
        imp = r.get("verdict") == "IMPOSSIBLE"
        if l == "CONFIRMED":
            tp, fn = tp + imp, fn + (not imp)
        elif l == "ACHIEVABLE":
            fp, tn = fp + imp, tn + (not imp)
        else:
            inc += 1
    return {"cases": len(rows), "confirmed": tp + fn, "achieved": fp + tn,
            "inconclusive_or_unexecuted": inc, "recall": _rate(tp, tp + fn),
            "false_rejections": _rate(fp, fp + tn),
            "decided_accuracy": _rate(tp + tn, tp + fn + fp + tn)}


def by(rows, lab, key) -> dict:
    g = defaultdict(list)
    for r in rows:
        g[key(r)].append(r)
    return {k: metrics(v, lab) for k, v in sorted(g.items())}


def score_run(run: Path) -> dict:
    frozen = json.loads((run / "frozen.json").read_text())
    cases = {c["id"]: c for c in frozen["cases"]}
    res = {r["case"]: r for r in json.loads((run / "results.json").read_text())}
    rows = [dict(res[c], **{k: cases[c].get(k) for k in ("stratum", "runtime", "domain")})
            for c in cases]
    batch = preq_batch(list(cases))
    out = {"method": frozen["method"], "valid_final": sum(r["valid"] for r in rows)}
    viol = violations()
    for scheme in ("L2", "strict"):
        lab = labels(scheme)
        m = {"all": metrics(rows, lab),
             "no_violations": metrics([r for r in rows if r["case"] not in viol], lab),
             "by_stratum": by(rows, lab, lambda r: r["stratum"]),
             "by_runtime": by(rows, lab, lambda r: r["runtime"]),
             "by_domain": by([r for r in rows if r["stratum"] == "real-nondev"], lab,
                             lambda r: r["domain"]),
             "by_blocker_kind": {k: _rate(
                 sum(1 for r in rows if lab.get(r["case"], {}).get("blocker_kind") == k
                     and lab[r["case"]]["label"] == "CONFIRMED"
                     and r.get("verdict") == "IMPOSSIBLE"),
                 sum(1 for r in rows if lab.get(r["case"], {}).get("blocker_kind") == k
                     and lab[r["case"]]["label"] == "CONFIRMED"))
                 for k in sorted(L2_CONFIRMING | {"network_or_service_unavailable"})},
             "prequential": {"batches_1_8": metrics([r for r in rows if batch[r["case"]] < 8], lab),
                             "batches_9_17": metrics([r for r in rows if batch[r["case"]] >= 8], lab)}}
        nd = m["by_stratum"].get("real-nondev", {}).get("decided_accuracy", {}).get("value")
        rts = [v["decided_accuracy"]["value"] for v in m["by_runtime"].values()]
        m["Q1_generalises"] = bool(nd is not None and nd >= 0.80
                                   and all(x is not None and x >= 0.75 for x in rts))
        out[scheme] = m
    (run / "div_metrics.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


def compare(a: Path, b: Path) -> dict:
    """Q2: method b (P2g + index) against method a (P2g) on the same cases."""
    ra = {r["case"]: r for r in json.loads((a / "results.json").read_text())}
    rb = {r["case"]: r for r in json.loads((b / "results.json").read_text())}
    out = {}
    for scheme in ("L2", "strict"):
        lab = labels(scheme)
        dec = [c for c in ra if lab.get(c, {}).get("label") in ("CONFIRMED", "ACHIEVABLE")]
        ok = lambda r, c: (r[c].get("verdict") == "IMPOSSIBLE") == (lab[c]["label"] == "CONFIRMED")
        better = sum(ok(rb, c) and not ok(ra, c) for c in dec)
        worse = sum(ok(ra, c) and not ok(rb, c) for c in dec)
        ma, mb = metrics(list(ra.values()), lab), metrics(list(rb.values()), lab)
        mt = [c for c in dec if lab[c]["blocker_kind"] == "missing_tool_in_runtime"
              and lab[c]["label"] == "CONFIRMED"]
        rec_mt = {k: _rate(sum(r[c].get("verdict") == "IMPOSSIBLE" for c in mt), len(mt))
                  for k, r in (("a", ra), ("b", rb))}
        d_rec = (mb["recall"]["value"] or 0) - (ma["recall"]["value"] or 0)
        d_mt = (rec_mt["b"]["value"] or 0) - (rec_mt["a"]["value"] or 0)
        out[scheme] = {
            "a": str(a.name), "b": str(b.name), "a_metrics": ma, "b_metrics": mb,
            "missing_tool_recall": rec_mt, "b_better": better, "b_worse": worse,
            "mcnemar_p": mcnemar_exact(better, worse),
            "criteria": {
                "recall_up_10pts_or_missing_tool_up_15pts":
                    d_rec >= 0.10 or (len(mt) >= 10 and d_mt >= 0.15),
                "false_rejections_up_at_most_2":
                    mb["false_rejections"]["k"] - ma["false_rejections"]["k"] <= 2,
                "decided_accuracy_not_lower":
                    (mb["decided_accuracy"]["value"] or 0) >= (ma["decided_accuracy"]["value"] or 0)}}
        out[scheme]["Q2_passes"] = all(out[scheme]["criteria"].values())
    (DIV / "comparison.json").write_text(json.dumps(out, indent=1) + "\n")
    return out


def main() -> None:
    runs = [Path(p) for p in sys.argv[1:]]
    for r in runs:
        m = score_run(r)
        print(r.name, json.dumps({k: m["L2"]["all"][k] for k in
                                  ("recall", "false_rejections", "decided_accuracy")}),
              "Q1:", m["L2"]["Q1_generalises"])
    if len(runs) == 2:
        c = compare(*runs)
        print(json.dumps({s: {"Q2": c[s]["Q2_passes"], **c[s]["criteria"],
                              "better": c[s]["b_better"], "worse": c[s]["b_worse"],
                              "p": c[s]["mcnemar_p"]} for s in c}, indent=1))


if __name__ == "__main__":
    main()
