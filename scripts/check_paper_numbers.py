#!/usr/bin/env python3
"""Check the numbers the paper states against the shipped results.

Two review rounds found stale figures in Section 10 -- right method, old
run -- because nothing tied a sentence in main.tex to the file it came
from. This does: paper/WIP/results/CLAIMS.json lists each checkable
number as (what it is, how to compute it from results/, the literal the
paper prints, a tolerance). A drift fails here instead of in review.

Only numbers that are mechanically derivable from a shipped results file
are listed. Numbers that need a model call, and prose judgements, are
not -- and are marked as such in the manifest so the gap is visible.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "paper" / "WIP" / "results"
MANIFEST = RESULTS / "CLAIMS.json"


def load(name: str):
    path = (RESULTS / name).resolve()
    if name.endswith(".jsonl"):
        return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return json.loads(path.read_text())


def _choices(steps: list) -> list:
    """Every choice node in a protocol, nested ones included."""
    out = []
    for s in steps:
        if "choice" in s:
            out.append(s["choice"])
            for br in s["choice"]["branches"].values():
                out += _choices(br)
        elif "rec" in s:
            out += _choices(s["rec"]["body"])
    return out


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return math.nan
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def main() -> int:
    claims = json.loads(MANIFEST.read_text())["claims"]
    env = {"load": load, "median": median, "_choices": _choices, "sum": sum, "len": len, "min": min,
           "max": max, "round": round, "abs": abs, "sorted": sorted, "set": set,
           "__builtins__": {"set": set, "sum": sum, "len": len, "min": min,
                            "max": max, "round": round, "abs": abs,
                            "sorted": sorted, "True": True, "False": False}}
    bad = []
    for c in claims:
        got = eval(c["compute"], env, env)   # noqa: S307 - our own manifest
        want, tol = c["paper"], c.get("tol", 0)
        ok = abs(got - want) <= tol
        if not ok:
            bad.append((c["what"], want, got, tol))
        print(f"{'ok ' if ok else 'BAD'} {c['what']}: paper {want}, data {got}")
    if bad:
        print(f"\n{len(bad)} of {len(claims)} numbers disagree with the shipped results:")
        for what, want, got, tol in bad:
            print(f"  {what}: paper says {want}, data says {got} (tolerance {tol})")
        return 1
    print(f"\nall {len(claims)} checkable numbers agree with the shipped results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
