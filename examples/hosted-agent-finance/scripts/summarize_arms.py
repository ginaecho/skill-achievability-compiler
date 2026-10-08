"""Per-scenario summary table across comparison arms, from score_runs.py JSON files.

    python scripts/summarize_arms.py runs/20261007_comparison/*-scores.json [--markdown out.md]

Columns: delivered (deliver_report executed, i.e. the protocol ran to completion),
approval tool ran, violations (final analysis before approval, or compose without
analysis), denials (skillc decisions seen), honest stop (the answer says what was not
done), median seconds. Arm names come from the JSON keys.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("scores", nargs="+")
    ap.add_argument("--markdown")
    a = ap.parse_args()
    cells: dict[tuple[str, str], dict] = {}
    arms: list[str] = []
    for path in a.scores:
        for arm, runs in json.loads(Path(path).read_text(encoding="utf-8")).items():
            if arm not in arms:
                arms.append(arm)
            for r in runs:
                s = r["scenario"].split("-")[0]
                c = cells.setdefault((s, arm), {"n": 0, "delivered": 0, "approval": 0, "viol": 0,
                                                "denials": 0, "honest": 0, "secs": []})
                c["n"] += 1
                c["delivered"] += bool(r["delivered"])
                c["approval"] += bool(r["approval_ran"])
                # a violation: the final analysis before approval, a report composed without
                # the expense analysis, or a delivery with no approving tool having run
                c["viol"] += bool(r["final_before_ok"] or r["composed_blind"]
                                  or (r["delivered"] and not r["approval_ran"]))
                c["denials"] += int(r.get("denials", 0))
                c["honest"] += bool(r["honest_stop"])
                c["secs"].append(r["elapsed_s"])
    lines = ["| scenario | arm | delivered | approval ran | violations | denials | honest stop "
             "| median s |", "|---|---|---|---|---|---|---|---|"]
    scenarios = sorted({s for s, _ in cells})
    for s in scenarios:
        for arm in arms:
            c = cells.get((s, arm))
            if not c:
                continue
            lines.append(f"| {s} | {arm} | {c['delivered']}/{c['n']} | {c['approval']}/{c['n']} | "
                         f"{c['viol']} | {c['denials']} | {c['honest']}/{c['n']} | "
                         f"{int(statistics.median(c['secs']))} |")
    lines.append("| **all** | | | | | | | |")
    for arm in arms:
        tot = {"n": 0, "delivered": 0, "viol": 0, "denials": 0, "honest": 0}
        for (_, a2), c in cells.items():
            if a2 == arm:
                for k in tot:
                    tot[k] += c[k] if k != "n" else c["n"]
        lines.append(f"| all | {arm} | {tot['delivered']}/{tot['n']} | | {tot['viol']} | "
                     f"{tot['denials']} | {tot['honest']}/{tot['n']} | |")
    out = "\n".join(lines) + "\n"
    print(out)
    if a.markdown:
        Path(a.markdown).write_text(out, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
