#!/usr/bin/env python3
"""Severity analysis with COMPLETE verdict recording over external choices.

Why this file exists.  `skillc.severity.SeverityAnalyzer.hazard_within` records a verdict for
every branch of an agent choice even after a hazard was found (its comment says so), but its
loop over the branches of an EXTERNAL choice returns at the first branch in which a hazard is
found, also while recording.  For a pack with external choices the recorded verdicts therefore
cover only the environment branches up to the first hazardous one.  (k* and the point of no
return are unaffected: they come from the budget scan, which needs only the first hazard.)

This module builds a subclass whose `hazard_within` is the tool's own source with exactly one
change: while recording, the loop over an external choice visits every branch and keeps the
first hazard it saw.  The source is taken from `skillc.severity` at import time (so the copy
cannot drift) and the substitution fails loudly if the tool's text changes.  Guards, `_record`,
severity classification and the budget scan are the tool's.  `skillc.severity` is not edited.

    PYTHONPATH=src python3 benchmarks/severity_real/analyze_all_worlds.py [case ...]

writes <case>/result_allworlds.json (default: every case whose pack has an external choice).
tests/test_severity.py checks that, on the packs without external choices, the result equals
the committed result.json of the stock tool.
"""
from __future__ import annotations
import inspect, json, sys, textwrap
from pathlib import Path

from skillc import severity as _sev
from skillc.pack import Pack

HERE = Path(__file__).resolve().parent

_OLD = """                    for label, br in body["branches"].items():
                        bst = _mk_state(cur.true_preds, cur.arith, cur.versions(),
                                        cur.path + (("env", label),))
                        found, wit, pnr = self.hazard_within(
                            list(br) + rest, bst, recenv, budget, loop_seen,
                            f"{node}/{label}", record)
                        if found:
                            return True, wit, pnr
                    return False, (), None
"""
_NEW = """                    first_env = None
                    for label, br in body["branches"].items():
                        bst = _mk_state(cur.true_preds, cur.arith, cur.versions(),
                                        cur.path + (("env", label),))
                        found, wit, pnr = self.hazard_within(
                            list(br) + rest, bst, recenv, budget, loop_seen,
                            f"{node}/{label}", record)
                        if found:
                            if not record:
                                return True, wit, pnr
                            first_env = first_env or (True, wit, pnr)
                    return first_env or (False, (), None)
"""


def _build():
    src = textwrap.dedent(inspect.getsource(_sev.SeverityAnalyzer.hazard_within))
    # the block sits two levels deeper than the dedented def; re-indent both sides alike
    old_d, new_d = _indent_like(src, _OLD), _indent_like(src, _NEW)
    if old_d not in src:
        raise RuntimeError("skillc.severity.hazard_within changed: update analyze_all_worlds.py")
    ns = dict(vars(_sev))
    exec(compile(src.replace(old_d, new_d), "<hazard_within with complete recording>", "exec"), ns)
    return ns["hazard_within"]


def _indent_like(dedented_src: str, block: str) -> str:
    # `block` was written for the original (class-level) indentation; remove the 4 spaces of the class body
    return "".join(line[4:] if line.startswith("    ") else line for line in block.splitlines(True))


class AllWorldsAnalyzer(_sev.SeverityAnalyzer):
    hazard_within = _build()


def analyze_all_worlds(pack: dict, kmax: int = 4):
    p = Pack.load({k: v for k, v in pack.items() if k != "irreversible"})
    return AllWorldsAnalyzer(p, kmax=kmax, irreversible=pack.get("irreversible")).run()


def _has_external(pack: dict) -> bool:
    return _sev._has_external(pack["protocol"])


def main(argv):
    cases = argv or [d.name for d in sorted(HERE.iterdir())
                     if (d / "pack.json").exists() and _has_external(json.loads((d / "pack.json").read_text()))]
    for c in cases:
        pack = json.loads((HERE / c / "pack.json").read_text())
        rep = analyze_all_worlds(pack).to_dict()
        (HERE / c / "result_allworlds.json").write_text(json.dumps(rep, indent=1) + "\n")
        print(c, rep["tolerance_degree"], rep["counts"])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
