#!/usr/bin/env python3
"""Check the numbers the paper states against the shipped results.

Two review rounds found stale figures in Section 10 -- right method, old
run -- because nothing tied a sentence in main.tex to the file it came
from. This does: paper/WIP/results/CLAIMS.json lists each checkable
number as (what it is, how to compute it from results/, the literal the
paper prints, a tolerance). A drift fails here instead of in review.

A claim's `compute` should read the same field the paper read, not
re-derive the number a different way: re-deriving once produced a
one-tenth-of-a-cent disagreement and a "correction" to a figure that was
right.

Only numbers that are mechanically derivable from a shipped results file
are listed. Numbers that need a model call, and prose judgements, are
not -- and are marked as such in the manifest so the gap is visible.

A claim may also carry `cite`: a list of {file, text} pairs whose text
must appear in that file. Without it the manifest only checks data
against data, and a paragraph can drift from the number it quotes -- which
is exactly how the artifact README came to contradict the paper.
Matching ignores how the text is wrapped (runs of whitespace compare
equal), so re-flowing a paragraph does not fail the check; the words and
figures must still appear, in that order, with nothing between them.
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "paper" / "WIP" / "results"
MANIFEST = RESULTS / "CLAIMS.json"


def flat(s: str) -> str:
    """Collapse whitespace, so a cited phrase survives being re-wrapped."""
    return " ".join(s.split())


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
    bad, missing, gone = [], [], []
    for c in claims:
        got = eval(c["compute"], env, env)   # noqa: S307 - our own manifest
        want, tol = c["paper"], c.get("tol", 0)
        ok = abs(got - want) <= tol
        if not ok:
            bad.append((c["what"], want, got, tol))
        for cite in c.get("cite", []):
            path = ROOT / cite["file"]
            if not path.is_file():
                gone.append((c["what"], cite["file"]))
                continue
            if flat(cite["text"]) not in flat(path.read_text(encoding="utf-8")):
                missing.append((c["what"], cite["file"], cite["text"]))
        print(f"{'ok ' if ok else 'BAD'} {c['what']}: paper {want}, data {got}")
    if gone:
        print(f"\n{len(gone)} claims cite a file that does not exist:")
        for what, f in gone:
            print(f"  {what}: no such file {f}")
    if missing:
        print(f"\n{len(missing)} quoted phrases are no longer in the file that quotes them:")
        for what, f, t in missing:
            print(f"  {what}: {f} no longer contains {t!r}")
    if bad:
        print(f"\n{len(bad)} of {len(claims)} numbers disagree with the shipped results:")
        for what, want, got, tol in bad:
            print(f"  {what}: paper says {want}, data says {got} (tolerance {tol})")
    if bad or missing or gone:
        return 1
    print(f"\nall {len(claims)} checkable numbers agree with the shipped results")
    return 0


if __name__ == "__main__":
    sys.exit(main())
