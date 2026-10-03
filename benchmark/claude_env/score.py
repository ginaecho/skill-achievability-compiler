"""Score skillc's verdicts against the blind, execution-verified ground truth.

    python benchmark/claude_env/score.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent


def main() -> None:
    skillc = {r["case"]: r for r in json.loads((HERE / "results" / "skillc.json").read_text())}
    truth = {p.stem: json.loads(p.read_text()) for p in sorted((HERE / "truth").glob("c*.json"))}
    cm = Counter((truth[c]["verdict"], skillc[c]["verdict"]) for c in truth)
    tp, fn = cm["BLOCKED", "BLOCKED"], cm["BLOCKED", "ACHIEVABLE"]
    fp, tn = cm["ACHIEVABLE", "BLOCKED"], cm["ACHIEVABLE", "ACHIEVABLE"]
    print(f"cases {len(truth)}   agree {tp + tn}   accuracy {(tp + tn) / len(truth):.0%}")
    print(f"truth BLOCKED:    skillc BLOCKED {tp:3}   skillc ACHIEVABLE {fn:3}  (missed)")
    print(f"truth ACHIEVABLE: skillc BLOCKED {fp:3}   skillc ACHIEVABLE {tn:3}"
          "  (false refutations on the left)")
    print(f"BLOCKED precision {tp / (tp + fp):.0%}   recall {tp / (tp + fn):.0%}")
    for c in truth:
        t, s = truth[c]["verdict"], skillc[c]["verdict"]
        if t != s:
            print(f"  {c} truth {t:<10} {truth[c]['blocking']}  "
                  f"skillc {s:<10} {skillc[c]['blocked']}")


if __name__ == "__main__":
    main()
