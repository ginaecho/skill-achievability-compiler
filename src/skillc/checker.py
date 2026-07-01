"""The trusted core: capability-guarded tolerant may-reachability.

Decides whether the goal of a pack is achievable, mirroring the mechanized
proof in proof/SkillAchievability.v:

  * The checker explores an abstract effect-transition system by *tolerant
    may-reachability* (exists-a-path / detours allowed / payload detail
    abstracted away).
  * STRIPS frame semantics: a predicate is false unless an action's effect
    establishes it.  A goal that needs `confirmation_sent`, with no capability
    that establishes it, is REFUTED (Coq: FlightInstance).
  * SOUND for refutation (Coq T1): an IMPOSSIBLE verdict is never wrong,
    relative to the declared capabilities + frame assumption.
  * INCOMPLETE for achievability (Coq T3): ACHIEVABLE means "structurally
    admissible", not "guaranteed" -- the residue is intent fidelity (top) and
    payload faithfulness (bottom), owned by other layers.

Verdicts:  ACHIEVABLE (+witness path)  |  IMPOSSIBLE (+reason, +frontier)
Reasons :  MISSING_CAPABILITY | BLOCKED_GUARD | GOAL_UNSAT | NON_PROJECTABLE
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import z3

from .formula import CMP
from .pack import Capability, Pack

REASONS = ("OK", "MISSING_CAPABILITY", "BLOCKED_GUARD", "GOAL_UNSAT",
           "NON_PROJECTABLE")


# --------------------------------------------------------------------------
# Symbolic world state  (frame semantics: preds concrete, arithmetic symbolic)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class State:
    true_preds: frozenset            # predicates currently true (frame: else false)
    arith: tuple                     # accumulated z3 constraints (path condition)
    version: tuple                   # SSA version per numeric var, as sorted items
    path: tuple                      # witness: actions/branches taken so far

    def versions(self) -> dict[str, int]:
        return dict(self.version)

    def cur(self, var: str) -> z3.ArithRef:
        v = self.versions().get(var, 0)
        return z3.Int(f"{var}__{v}")


def _mk_state(preds, arith, version: dict[str, int], path) -> State:
    return State(frozenset(preds), tuple(arith),
                 tuple(sorted(version.items())), tuple(path))


def eval_expr(e: Any, st: State) -> z3.ArithRef:
    if isinstance(e, int):
        return z3.IntVal(e)
    if isinstance(e, str):
        return st.cur(e)
    if isinstance(e, dict):
        if "+" in e:
            return eval_expr(e["+"][0], st) + eval_expr(e["+"][1], st)
        if "-" in e:
            return eval_expr(e["-"][0], st) - eval_expr(e["-"][1], st)
        if "*" in e:
            return eval_expr(e["*"][0], st) * eval_expr(e["*"][1], st)
    raise ValueError(f"bad expr: {e!r}")


def eval_formula(f: Any, st: State) -> z3.BoolRef:
    """Compile a formula against concrete predicate truth + SSA arith vars."""
    if f is True:
        return z3.BoolVal(True)
    if f is False:
        return z3.BoolVal(False)
    if isinstance(f, str):
        return z3.BoolVal(f in st.true_preds)
    if isinstance(f, dict):
        if "and" in f:
            return z3.And([eval_formula(x, st) for x in f["and"]])
        if "or" in f:
            return z3.Or([eval_formula(x, st) for x in f["or"]])
        if "not" in f:
            return z3.Not(eval_formula(f["not"], st))
        if "cmp" in f:
            lhs, op, rhs = f["cmp"]
            return CMP[op](eval_expr(lhs, st), eval_expr(rhs, st))
    raise ValueError(f"bad formula: {f!r}")


def _sat(constraints: list) -> bool:
    s = z3.Solver()
    s.add(*constraints)
    return s.check() == z3.sat


def guard_satisfiable(st: State, cap: Capability) -> bool:
    return _sat(list(st.arith) + [eval_formula(cap.pre, st)])


def apply_effect(st: State, cap: Capability) -> State:
    new_true = set(st.true_preds)
    for a in cap.add:
        new_true.add(a)
    for d in cap.dele:
        new_true.discard(d)
    new_version = st.versions()
    new_arith = list(st.arith)
    # deterministic assignments  v := expr  (RHS evaluated in the OLD state)
    for v, expr in cap.assigns.items():
        rhs = eval_expr(expr, st)
        new_version[v] = new_version.get(v, 0) + 1
        new_arith.append(z3.Int(f"{v}__{new_version[v]}") == rhs)
    # nondeterministic assignments  v := *  with a constraint over the NEW value
    for v, constr in cap.nondet.items():
        new_version[v] = new_version.get(v, 0) + 1
        tmp = _mk_state(st.true_preds, new_arith, new_version, st.path)
        new_arith.append(eval_formula(constr, tmp))
    return _mk_state(new_true, new_arith, new_version,
                     st.path + (("act", cap.name),))


def initial_state(p: Pack) -> State:
    st0 = _mk_state(p.init_true, (), {}, ())
    cons = [eval_formula(c, st0) for c in p.init_constraints]
    return _mk_state(p.init_true, cons, {}, ())


# --------------------------------------------------------------------------
# Projectability (structural knowledge-of-choice / handoff check)
# --------------------------------------------------------------------------

def roles_acting(steps: list[dict]) -> set[str]:
    out: set[str] = set()
    for s in steps:
        if "act" in s:
            out.add(s["act"].get("by", "?"))
        if "msg" in s:
            out.add(s["msg"]["from"])
        if "choice" in s:
            out.add(s["choice"]["by"])
            for br in s["choice"]["branches"].values():
                out |= roles_acting(br)
    return out


def message_receivers(steps: list[dict]) -> set[str]:
    """Roles that receive some message inside a branch."""
    out: set[str] = set()
    for s in steps:
        if "msg" in s:
            out.add(s["msg"]["to"])
        if "choice" in s:
            for br in s["choice"]["branches"].values():
                out |= message_receivers(br)
    return out


def check_projectable(steps: list[dict]) -> Optional[str]:
    """Return None if OK, else a human-readable non-projectability reason.

    Knowledge-of-choice: when role p selects among branches, any *other* role
    that must act inside a branch must receive a branch-distinguishing message
    before acting.  Otherwise it cannot know how to behave -> deadlock / wrong
    handoff (the classic unobserved-choice freeze).

    This is a structural, focused check on the unobserved-choice family, not a
    full MPST projection-with-merge engine.
    """
    for s in steps:
        if "choice" in s:
            chooser = s["choice"]["by"]
            branches = s["choice"]["branches"]
            for label, br in branches.items():
                actors = roles_acting(br)
                informed = message_receivers(br) | {chooser}
                uninformed = actors - informed
                if uninformed:
                    who = sorted(uninformed)[0]
                    return (f"role '{who}' must act in branch '{label}' chosen by "
                            f"'{chooser}' but receives no message distinguishing "
                            f"that branch (unobserved choice -> deadlock/handoff "
                            f"failure)")
            for br in branches.values():
                r = check_projectable(br)
                if r:
                    return r
    return None


# --------------------------------------------------------------------------
# Verdict + checker
# --------------------------------------------------------------------------

@dataclass
class Verdict:
    achievable: bool
    reason: str = "OK"
    detail: str = ""
    witness: tuple = ()          # action/branch path for ACHIEVABLE
    frontier: tuple = ()         # blocking info for IMPOSSIBLE

    @property
    def label(self) -> str:
        return "ACHIEVABLE" if self.achievable else "IMPOSSIBLE"

    def to_dict(self) -> dict:
        return {
            "verdict": self.label,
            "reason": self.reason,
            "detail": self.detail,
            "witness": [list(w) for w in self.witness],
            "frontier": list(self.frontier),
        }


class Checker:
    def __init__(self, pack: Pack):
        self.p = pack
        self.blocked: list[str] = []     # frontier accumulation

    def run(self) -> Verdict:
        # 1. capability existence (no hallucinated tools)
        missing = self._missing_caps(self.p.protocol)
        if missing:
            return Verdict(False, "MISSING_CAPABILITY",
                           f"protocol invokes undeclared capabilities: {sorted(missing)}",
                           frontier=tuple(sorted(missing)))
        # 2. projectability / handoff
        proj = check_projectable(self.p.protocol)
        if proj:
            return Verdict(False, "NON_PROJECTABLE", proj)
        # 3. tolerant may-reachability of the goal
        ok, end_state = self._reach(self.p.protocol, initial_state(self.p))
        if ok:
            return Verdict(True, "OK", "goal reachable along witness path",
                           witness=end_state.path)
        if self.blocked:
            uniq = tuple(dict.fromkeys(self.blocked))
            return Verdict(False, "BLOCKED_GUARD", "; ".join(uniq), frontier=uniq)
        return Verdict(False, "GOAL_UNSAT",
                       "protocol terminates but no run satisfies the goal "
                       "(goal predicate never established / refinement unsatisfiable)")

    def _missing_caps(self, steps: list[dict]) -> set[str]:
        out: set[str] = set()
        for s in steps:
            if "act" in s and s["act"]["cap"] not in self.p.capabilities:
                out.add(s["act"]["cap"])
            if "choice" in s:
                for br in s["choice"]["branches"].values():
                    out |= self._missing_caps(br)
        return out

    def _goal_sat(self, st: State) -> bool:
        return _sat(list(st.arith) + [eval_formula(self.p.goal, st)])

    def _reach(self, steps: list[dict], st: State) -> tuple[bool, State]:
        """(reached_goal, witnessing/end state).  Existential over branches."""
        cur = st
        for i, s in enumerate(steps):
            if "goal" in s:                        # explicit goal marker
                if self._goal_sat(cur):
                    return True, cur
                # else continue; the goal may be established later
            elif "msg" in s:
                cur = _mk_state(cur.true_preds, cur.arith, cur.versions(),
                                cur.path + (("msg", s["msg"]["label"]),))
            elif "act" in s:
                cap = self.p.capabilities[s["act"]["cap"]]
                if not guard_satisfiable(cur, cap):
                    self.blocked.append(
                        f"capability '{cap.name}' guard never satisfiable on "
                        f"this path (pre={cap.pre!r})")
                    return False, cur              # mandatory action blocked
                cur = apply_effect(cur, cap)
            elif "choice" in s:
                # existential: succeed if ANY branch + continuation reaches goal
                rest = steps[i + 1:]
                for label, br in s["choice"]["branches"].items():
                    branch_state = _mk_state(cur.true_preds, cur.arith,
                                             cur.versions(),
                                             cur.path + (("choose", label),))
                    ok, end = self._reach(list(br) + rest, branch_state)
                    if ok:
                        return True, end
                return False, cur
        # end of this block: check goal at terminal
        if self._goal_sat(cur):
            return True, cur
        return False, cur


def check(pack: dict | Pack) -> Verdict:
    """Check a pack (dict or Pack) and return the Verdict."""
    p = pack if isinstance(pack, Pack) else Pack.load(pack)
    return Checker(p).run()
