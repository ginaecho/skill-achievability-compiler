"""Label items for the div execution reports (runs/20260928_div/labels, same prompt as
the prior reports) and adjudication items for its achieved reports.

  python scripts/div_labels.py items      # labels/items/<case>.json + labels/batch_div_*.json
  python scripts/div_labels.py items_gr   # the same for the gr test reports (batch_gr_*.json)
  python scripts/div_labels.py adjudicate # adjudication/batch_*.json (achieved reports only)
  python scripts/div_labels.py collect    # adjudication/out/*.json -> adjudication.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))
from scripts.benchmark_ce_runtime import _div, _gr, skill_path  # noqa: E402
from skillc.frontend.policyindex import extract_terms  # noqa: E402

DIV = ROOT / "runs" / "20260928_div"


def items(cases=None, execution: Path = DIV / "execution", prefix: str = "div") -> None:
    new = []
    for c in (cases if cases is not None else _div()):
        rep = execution / f"{c['id']}.json"
        out = DIV / "labels" / "items" / f"{c['id']}.json"
        if not rep.exists() or out.exists():
            continue
        text = skill_path(c).read_text(encoding="utf-8")
        out.write_text(json.dumps({
            "skill": c["id"], "runtime": c["runtime"], "skill_path": str(skill_path(c)),
            "report_path": str(rep),
            "candidates": [t["term"] for t in extract_terms(text)]}, indent=1) + "\n")
        new.append(c["id"])
    k0 = len(list((DIV / "labels").glob(f"batch_{prefix}_*.json")))
    for i in range(0, len(new), 10):
        (DIV / "labels" / f"batch_{prefix}_{k0 + i // 10:02d}.json").write_text(
            json.dumps(new[i:i + 10]) + "\n")
    print(len(new), "new items")


def adjudicate() -> None:
    d = DIV / "adjudication"
    (d / "out").mkdir(parents=True, exist_ok=True)
    ach = []
    for c in _div():
        rep = DIV / "execution" / f"{c['id']}.json"
        if rep.exists() and json.loads(rep.read_text()).get("outcome") == "achieved":
            ach.append({"case": c["id"], "runtime": c["runtime"],
                        "skill_path": str(skill_path(c)), "report_path": str(rep)})
    for i in range(0, len(ach), 12):
        (d / f"batch_{i // 12:02d}.json").write_text(json.dumps(ach[i:i + 12], indent=1) + "\n")
    print(len(ach), "achieved reports")


def collect() -> None:
    out = {}
    for f in sorted((DIV / "adjudication" / "out").glob("*.json")):
        out[f.stem] = json.loads(f.read_text())
    (DIV / "adjudication.json").write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    print(len(out), "adjudicated;", sum(v["verdict"] == "simulated" for v in out.values()),
          "simulated")


if __name__ == "__main__":
    {"items": items, "adjudicate": adjudicate, "collect": collect,
     "items_gr": lambda: items(_gr(), ROOT / "runs" / "20261001_gr" / "execution", "gr")
     }[sys.argv[1]]()
