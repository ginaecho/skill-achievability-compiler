"""Term-requirement dataset and splits for the small-model arms (runs/20260928_div/PLAN.md).

One row per labelled (report, term) with keep=true: the term, the skill line it occurs
on (context), the report's runtime, the skill's GitHub organisation, and the labels
`cls`, `core`, `blocked`. Writes runs/20260928_div/slm/{rows.jsonl, splits.json, stats.json}.

Splits:
  leave_org_out  one fold per organisation with >= 10 rows: test = that org's rows
  unseen_terms   terms hashed into 5 folds (sha256("term:" + term)); a test term never
                 occurs in training, in any skill
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skillc.frontend.policyindex import CLASSES, norm  # noqa: E402

DIV = ROOT / "runs" / "20260928_div"
OUT = DIV / "slm"


def context(text: str, term: str) -> str:
    low = term.lower()
    for line in text.splitlines():
        if low in line.lower():
            return re.sub(r"\s+", " ", line.strip())[:300]
    return ""


def rows() -> list[dict]:
    out = []
    for f in sorted((DIV / "labels" / "out").glob("*.json")):
        item = json.loads((DIV / "labels" / "items" / f.name).read_text())
        text = Path(item["skill_path"]).read_text(encoding="utf-8", errors="replace")
        skill = item["skill"].split("@")[0]
        for t in json.loads(f.read_text())["terms"]:
            if not t.get("keep"):
                continue
            term = norm(t["term"])
            out.append({"report": f.stem, "skill": skill, "org": skill.split("__")[0],
                        "runtime": item["runtime"], "term": term,
                        "context": context(text, term),
                        "cls": t["cls"] if t["cls"] in CLASSES else "none",
                        "core": bool(t.get("core")), "blocked": bool(t.get("blocked")),
                        "source": "div" if "@" in f.stem else "prior"})
    return out


def splits(data: list[dict]) -> dict:
    by_org = defaultdict(list)
    for i, r in enumerate(data):
        by_org[r["org"]].append(i)
    loo = {o: ix for o, ix in sorted(by_org.items()) if len(ix) >= 10}
    fold = lambda t: int(hashlib.sha256(("term:" + t).encode()).hexdigest(), 16) % 5
    unseen = {str(k): [i for i, r in enumerate(data) if fold(r["term"]) == k] for k in range(5)}
    return {"leave_org_out": loo, "unseen_terms": unseen}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    data = rows()
    (OUT / "rows.jsonl").write_text("".join(json.dumps(r) + "\n" for r in data))
    sp = splits(data)
    (OUT / "splits.json").write_text(json.dumps(sp) + "\n")
    stats = {"rows": len(data), "terms": len({r["term"] for r in data}),
             "reports": len({r["report"] for r in data}),
             "by_cls": dict(Counter(r["cls"] for r in data).most_common()),
             "core": sum(r["core"] for r in data), "blocked": sum(r["blocked"] for r in data),
             "by_source": dict(Counter(r["source"] for r in data)),
             "leave_org_out_folds": {o: len(ix) for o, ix in sp["leave_org_out"].items()},
             "unseen_term_folds": {k: len(ix) for k, ix in sp["unseen_terms"].items()}}
    (OUT / "stats.json").write_text(json.dumps(stats, indent=1) + "\n")
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
