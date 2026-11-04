#!/usr/bin/env python3
"""Every Coq result the paper cites must exist and be axiom-free.

The paper's claim is not just "these theorems are proved" but "all of them
are Print Assumptions closed".  A citation that names a result no harness
checks is a hole in that claim, and a citation that names nothing at all is
worse.  This script checks both directions and is cheap enough to run on
every commit.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEX = ROOT / "paper" / "WIP" / "main.tex"
PROOF = ROOT / "paper" / "WIP" / "proof"

DEFINER = ("Theorem|Lemma|Corollary|Definition|Fixpoint|Inductive|CoInductive|"
           "Record|Proposition|Remark|Example|Instance")
# a citation may also name a constructor of an inductive, which is written
# `| Name :` inside the declaration rather than at the head of a sentence
CONSTRUCTOR = r"^\s*\|\s*{name}\s*:"


def cited_names(tex: str) -> list[str]:
    names = {n.replace("\\_", "_") for n in re.findall(r"\\coqok\{([^}]*)\}", tex)}
    names.discard("name")            # the legend, not a citation
    return sorted(names)


def main() -> int:
    tex = TEX.read_text(encoding="utf-8")
    src = "\n".join(p.read_text(encoding="utf-8") for p in sorted(PROOF.glob("*.v")))
    checks = "\n".join(p.read_text(encoding="utf-8")
                       for p in sorted(PROOF.glob("check_*.v")))
    checked = set(re.findall(r"Print Assumptions\s+([A-Za-z0-9_']+)\s*\.", checks))

    names = cited_names(tex)
    def defined(n: str) -> bool:
        return bool(re.search(rf"^\s*({DEFINER})\s+{re.escape(n)}\b", src, re.M)
                    or re.search(CONSTRUCTOR.format(name=re.escape(n)), src, re.M))

    undefined = [n for n in names if not defined(n)]
    unchecked = [n for n in names if n not in checked]

    print(f"{len(names)} Coq results cited by the paper")
    for label, bad in (("not defined anywhere in proof/", undefined),
                       ("defined but in no Print Assumptions harness", unchecked)):
        if bad:
            print(f"  {len(bad)} {label}:")
            for n in bad:
                print(f"    {n}")
    if undefined or unchecked:
        return 1
    print("  all defined, all covered by a Print Assumptions harness")
    return 0


if __name__ == "__main__":
    sys.exit(main())
