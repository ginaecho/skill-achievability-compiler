"""Two baselines for the checker, on the same bound pack (experiment R,
runs/20261015_review_response/PLAN.md, arms P and T).

  planner_only(pack)                 P: goal reachability over the capability
                                     layer alone (STRIPS, no protocol);
  tool_lint(pack, withdrawn, blocked) T: refute iff a Tool the protocol invokes
                                     was withdrawn or blocked by the binder.

Both are pure functions of a pack that passed `validate_pack`.  They exist to
show what each layer of the checker adds: T sees only the runtime binding, P
adds effects and preconditions, the checker adds protocol order, roles,
messages and typing.

P is a delete-relaxed forward fixpoint.  Starting from `init_true`, a
capability is enabled when its precondition is satisfiable with every atom
not yet reachable pinned FALSE and every reachable atom left free; its `add`
atoms become reachable.  Deletes are ignored and every numeric comparison is
a free Boolean, so the reachable set over-approximates every run of every
protocol over the capabilities.  P answers IMPOSSIBLE iff the goal is
unsatisfiable under the same pinning (z3, exactly as the checker's
protocol-independent refutation); otherwise ACHIEVABLE.  Protocol order,
roles, messages, choices and typing are ignored by construction.
"""
from __future__ import annotations

from itertools import count
from typing import Any

import z3

from .formula import atoms, compile_formula
from .pack import iter_steps, validate_pack


def _satisfiable(f: Any, reachable: set) -> bool:
    fresh = count()
    expr = compile_formula(
        f,
        pred=lambda n: z3.Bool(f"p::{n}") if n in reachable else z3.BoolVal(False),
        cmp=lambda *_: z3.Bool(f"cmp::{next(fresh)}"))
    s = z3.Solver()
    s.add(expr)
    return s.check() == z3.sat


def planner_only(pack: dict) -> dict:
    """STRIPS (delete-relaxed) reachability of the goal; see the module doc."""
    validate_pack(pack)
    reachable = set(pack.get("init_true", []))
    remaining = dict(pack["capabilities"])
    fired: list = []
    while True:
        enabled = [n for n, c in remaining.items()
                   if _satisfiable(c.get("pre", True), reachable)]
        if not enabled:
            break
        for n in enabled:
            reachable.update(remaining.pop(n).get("add", []))
            fired.append(n)
    if _satisfiable(pack["goal"], reachable):
        return {"label": "ACHIEVABLE", "reason": "OK", "frontier": [],
                "enabled": sorted(fired)}
    return {"label": "IMPOSSIBLE", "reason": "GOAL_UNSAT",
            "frontier": sorted(atoms(pack["goal"]) - reachable),
            "enabled": sorted(fired)}


def invoked_tools(pack: dict) -> list:
    """Tools invoked by an `act` step anywhere in the protocol."""
    return sorted({s["act"]["cap"] for s in iter_steps(pack["protocol"]) if "act" in s})


def tool_lint(pack: dict, withdrawn: dict, blocked: dict) -> dict:
    """IMPOSSIBLE iff a Tool the protocol invokes was withdrawn (its `via` is
    not a runtime tool) or blocked (it needs a resource the runtime does not
    grant).  Everything else in the pack is ignored."""
    validate_pack(pack)
    dead = set(withdrawn or {}) | set(blocked or {})
    hit = [t for t in invoked_tools(pack) if t in dead]
    if hit:
        return {"label": "IMPOSSIBLE",
                "reason": "WITHDRAWN" if any(t in (withdrawn or {}) for t in hit)
                else "BLOCKED", "frontier": hit}
    return {"label": "ACHIEVABLE", "reason": "OK", "frontier": []}
