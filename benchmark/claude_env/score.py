"""Score skillc's verdicts against the blind, execution-verified ground truth.

    python benchmark/claude_env/score.py [--set DIR] [--results FILE]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent


def score(truth: dict, skillc: dict) -> dict:
    cm = Counter((truth[c]["verdict"], skillc[c]["verdict"]) for c in truth)
    tp, fn = cm["BLOCKED", "BLOCKED"], cm["BLOCKED", "ACHIEVABLE"]
    fp, tn = cm["ACHIEVABLE", "BLOCKED"], cm["ACHIEVABLE", "ACHIEVABLE"]
    return {"cases": len(truth), "tp": tp, "fn": fn, "fp": fp, "tn": tn,
            "accuracy": (tp + tn) / len(truth), "precision": tp / (tp + fp) if tp + fp else 0,
            "recall": tp / (tp + fn) if tp + fn else 0,
            "always_achievable": (fp + tn) / len(truth)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", type=Path, default=HERE)
    ap.add_argument("--results", type=Path)
    args = ap.parse_args()
    results = args.results or args.set / "results" / "skillc.json"
    skillc = {r["case"]: r for r in json.loads(results.read_text())}
    truth = {p.stem: json.loads(p.read_text())
             for p in sorted((args.set / "truth").glob("c*.json"))}
    r = score(truth, skillc)
    print(f"cases {r['cases']}   agree {r['tp'] + r['tn']}   accuracy {r['accuracy']:.0%}"
          f"   (always ACHIEVABLE would score {r['always_achievable']:.0%})")
    print(f"truth BLOCKED:    skillc BLOCKED {r['tp']:3}   skillc ACHIEVABLE {r['fn']:3}  (missed)")
    print(f"truth ACHIEVABLE: skillc BLOCKED {r['fp']:3}   skillc ACHIEVABLE {r['tn']:3}"
          "  (false refutations on the left)")
    print(f"BLOCKED precision {r['precision']:.0%}   recall {r['recall']:.0%}")
    for c in truth:
        t, s = truth[c]["verdict"], skillc[c]["verdict"]
        if t != s:
            print(f"  {c} truth {t:<10} {truth[c]['blocking']}  "
                  f"skillc {s:<10} {skillc[c]['blocked']}")


if __name__ == "__main__":
    main()
