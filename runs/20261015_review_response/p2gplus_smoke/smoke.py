"""P2g+ smoke test on the four set2 documents that motivated Addendum B (consumed
data: this is a check that the fixes address the examples, not an evaluation).

One sample per case, gpt-5.4 on Azure OpenAI, runtime claude-code-cloud, prompt
ce_runtime_messages(version="p2g+"), the P2g loop of frontend.llm.compact_ce_rounds
(two located-error retries, one guarded repair).  Writes <case>.ce and <case>.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "src"))

from skillc.frontend.llm import _analyze, compact_ce_rounds  # noqa: E402
from skillc.frontend.prompts import ce_runtime_messages  # noqa: E402
from skillc.frontend.runtime import load_runtime  # noqa: E402

CASES = ("c045", "c073", "c013", "c002")
SET2 = ROOT / "benchmark" / "claude_env" / "set2"
OLD = ROOT / "runs" / "20261015_cost" / "main" / "gated"
OUT = Path(__file__).resolve().parent
MODEL = "gpt-5.4"


def vd(v) -> dict | None:
    return None if v is None else {"label": v.label, "reason": v.reason,
                                   "protocol": v.protocol, "frontier": list(v.frontier)}


def main() -> None:
    rt = load_runtime("claude-code-cloud")
    rows = []
    for case in CASES:
        text = (SET2 / "cases" / f"{case}.md").read_text(encoding="utf-8")
        truth = json.loads((SET2 / "truth" / f"{case}.json").read_text(encoding="utf-8"))
        old = json.loads((OLD / f"{case}.json").read_text(encoding="utf-8"))
        system, user = ce_runtime_messages(text, rt, version="p2g+")
        res = compact_ce_rounds(system, user, rt, model=MODEL, provider="azure-openai",
                                retries=2, repair=True)
        # the verdict before any repair (the old gated arm had no repair round)
        first_valid = next((r for r in res["rounds"] if r["ok"] and r["kind"] != "repair"),
                           None)
        pre = _analyze(first_valid["reply"], rt)["verdict"] if first_valid else None
        if res["ok"]:
            (OUT / f"{case}.ce").write_text(res["ce_text"], encoding="utf-8")
        row = {"case": case, "truth": truth["verdict"],
               "old_verdict": old["verdict"], "old_error": old.get("error"),
               "new_verdict_before_repair": vd(pre), "new_verdict": vd(res["verdict"]),
               "ok": res["ok"], "error": res["error"], "repaired": res["repaired"],
               "repair_rejected": res["repair_rejected"],
               "rounds": res["rounds"], "system": system, "user": user,
               "model": MODEL, "runtime": rt.name, "prompt_version": "p2g+"}
        (OUT / f"{case}.json").write_text(json.dumps(row, indent=1, ensure_ascii=False),
                                          encoding="utf-8")
        rows.append({k: row[k] for k in ("case", "truth", "ok", "repaired", "error")}
                    | {"old": old["verdict"] and old["verdict"]["label"] + " "
                       + old["verdict"]["reason"],
                       "before_repair": pre and f"{pre.label} {pre.reason}",
                       "final": res["verdict"] and
                       f"{res['verdict'].label} {res['verdict'].reason}",
                       "rounds": [r["kind"] for r in res["rounds"]]})
        print(json.dumps(rows[-1]), flush=True)
    (OUT / "summary.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
