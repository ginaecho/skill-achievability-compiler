#!/usr/bin/env python3
"""Compare benchmarks/severity_real/<case>/result.json with <case>/EXPECTED.md.

Reads only the two files (no analysis is run).  For a case with external choices there is also
<case>/result_allworlds.json (analyze_all_worlds.py: the same analysis with every environment
branch recorded); it is compared the same way and printed on a second line.  Prints per-case agreement and
every disagreement; exit status is 0 regardless (disagreements are classified by hand
in FINDINGS.md).  `--json` prints a machine-readable summary.
"""
from __future__ import annotations
import json, re, sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent


class Atoms(dict):
    def __missing__(self, k):
        return False


def parse_expected(text: str) -> dict:
    exp = {"rows": []}
    m = re.search(r"^- k\*: (\S+)", text, re.M); exp["k"] = m.group(1) if m else None
    m = re.search(r"^- PNR: (\S+)", text, re.M); exp["pnr"] = m.group(1) if m else None
    sect = text.split("## Per-branch expectations", 1)[1]
    for line in sect.splitlines():
        if not line.startswith("|") or line.startswith("|---") or line.startswith("| branch"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        exp["rows"].append({"branch": cells[0], "cond": cells[1], "sev": cells[2]})
    return exp


def compare(case_dir: Path, result_name: str = "result.json") -> dict:
    exp = parse_expected((case_dir / "EXPECTED.md").read_text())
    res = json.loads((case_dir / result_name).read_text())
    out = {"case": case_dir.name, "result": result_name, "mismatches": [], "unmatched": [], "unobserved": [], "verdicts": 0, "agree": 0}
    seen = set()
    for v in res["verdicts"]:
        out["verdicts"] += 1
        atoms = Atoms({a: True for a in v["state"]})
        hit = None
        for i, r in enumerate(exp["rows"]):
            if r["branch"] == v["branch"] and (not r["cond"] or eval(r["cond"], {"__builtins__": {}}, atoms)):
                hit = i; break
        if hit is None:
            out["unmatched"].append({"branch": v["branch"], "state": v["state"], "got": v["severity"]}); continue
        seen.add(hit)
        r = exp["rows"][hit]
        if r["sev"] == v["severity"]:
            out["agree"] += 1
        else:
            out["mismatches"].append({"branch": v["branch"], "cond": r["cond"], "expected": r["sev"],
                                      "got": v["severity"], "state": v["state"]})
    for i, r in enumerate(exp["rows"]):
        if i not in seen:
            out["unobserved"].append(r)
    k = res["tolerance_degree"]; k = ">=5" if k is None else str(k)
    out["k_expected"], out["k_got"] = exp["k"], k
    out["pnr_expected"], out["pnr_got"] = exp["pnr"], res["pnr_action"]
    out["k_ok"] = exp["k"] == k
    out["pnr_ok"] = exp["pnr"] == res["pnr_action"]
    out["all_ok"] = (not out["mismatches"] and not out["unmatched"] and not out["unobserved"]
                     and out["k_ok"] and out["pnr_ok"])
    return out


def main(argv):
    rows = []
    for d in sorted(HERE.iterdir()):
        if (d / "EXPECTED.md").exists() and (d / "result.json").exists():
            rows.append(compare(d))
            if (d / "result_allworlds.json").exists():
                rows.append(compare(d, "result_allworlds.json"))
    if "--json" in argv:
        print(json.dumps(rows, indent=1)); return 0
    for r in rows:
        tag = "" if r["result"] == "result.json" else " [all worlds]"
        print(f"{r['case']}{tag}: verdicts {r['agree']}/{r['verdicts']} agree; k* exp {r['k_expected']} got {r['k_got']}; "
              f"PNR exp {r['pnr_expected']} got {r['pnr_got']}; {'AGREE' if r['all_ok'] else 'DISAGREE'}")
        for x in r["mismatches"]: print("   mismatch", x)
        for x in r["unmatched"]: print("   unmatched", x)
        for x in r["unobserved"]: print("   unobserved row", x)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
