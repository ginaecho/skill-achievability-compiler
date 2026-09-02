#!/usr/bin/env python3
"""The cheapest baseline: a grep.

A reviewer's fair objection to Finding 5 is that most of the checker's
refutations are a capability set-difference anyone could compute with a regular
expression: does the document contain a shell-looking code fence, and does the
runtime lack a shell? This script implements exactly that baseline and scores
it against the checker on the ground-truth configurations of
scripts/llm_judge_baseline.py, so the paper can say how much of its own
evaluation a grep already explains -- and which cases it does not.
"""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skillc.profiles import load_profile
from skillc.frontend.markdown import compile_file
from skillc.checker import check
sys.path.insert(0, str(ROOT / "scripts"))
import importlib.util
spec = importlib.util.spec_from_file_location("judge", ROOT / "scripts" / "llm_judge_baseline.py")
judge = importlib.util.module_from_spec(spec); spec.loader.exec_module(judge)

FENCE = re.compile(r"^(```+|~~~+)\s*(bash|sh|shell|zsh|console|python|py|node|javascript)?\b", re.M | re.I)
RUN = re.compile(r"\b(run|execute|invoke)\b[^\n]{0,40}`", re.I)


def grep_verdict(text: str, runtime: str) -> bool:
    """Achievable unless the document looks like it needs a shell the runtime lacks."""
    if runtime != "no-shell":
        return True
    needs_shell = bool(FENCE.search(text)) or bool(RUN.search(text))
    return not needs_shell


def main() -> int:
    items = judge.ground_truth()
    rows, t = [], 0.0
    for it in items:
        text = (ROOT / it["skill"]).read_text(encoding="utf-8")
        t0 = time.perf_counter()
        g = grep_verdict(text, it["runtime"])
        t += time.perf_counter() - t0
        c = check(compile_file(ROOT / it["skill"], load_profile(judge.RUNTIME_PROFILE[it["runtime"]])).pack).achievable
        rows.append({**{k: it[k] for k in ("skill", "runtime", "truth", "source")},
                     "grep": g, "grep_correct": g == it["truth"],
                     "checker": c, "checker_correct": c == it["truth"]})
    res = {"n": len(rows),
           "grep_correct": sum(r["grep_correct"] for r in rows),
           "checker_correct": sum(r["checker_correct"] for r in rows),
           "grep_ms": round(t * 1000, 2),
           "disagree": [r for r in rows if r["grep"] != r["checker"]],
           "grep_wrong": [r for r in rows if not r["grep_correct"]],
           "rows": rows}
    json.dump(res, open(ROOT / "paper" / "WIP" / "results" / "grep_baseline.json", "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k not in ("rows", "disagree", "grep_wrong")}, indent=1))
    print("\ngrep is wrong on:")
    for r in res["grep_wrong"]:
        print(f"  {r['skill']:60s} {r['runtime']:8s} truth={r['truth']} grep={r['grep']} checker={r['checker']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
