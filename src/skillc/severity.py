"""Severity analysis: what does a WRONG CHOICE cost?

The achievability checker decides whether a goal is reachable.  This module
asks a different question of the same pack: at every choice the protocol
offers, what happens if the agent takes the branch it should NOT have taken?

    Benign        the goal is still reachable afterwards (a detour)
    Futile        the goal is lost, but nothing irreversible happened
    Catastrophic  an irreversible effect fires after which the goal is
                  unreachable -- a POINT OF NO RETURN is crossed

and, with a budget k of misselections, whether the protocol is
k-misselection-tolerant: no run with at most k wrong choices reaches a
catastrophe.  The largest such k is the pack's TOLERANCE DEGREE k*.

Default instantiation (needs no annotation beyond what a pack already has):

  * intended branch  := a branch from whose residual the goal is still
                        reachable (the rational-choice guard);
  * hazard           := an action that PERMANENTLY deletes an atom (no
                        capability in Gamma re-establishes it) fired from a
                        configuration after which the goal is unreachable
                        ("burned the bridge, and still lost").

Both may be overridden by an explicit `guards` / `hazard` declaration on
the pack.  The analysis runs over the checker's own widened abstraction
(predicates concrete, numerics symbolic and widened at loop heads), so
Catastrophic verdicts inherit the checker's refutation soundness and
Benign verdicts its over-approximation.

Mechanized counterpart: paper/WIP/proof/Severity.v (T-Choice-Safe, sound and
complete for k-bounded hazard-freedom), Bridge.v (sessions typed against a
k-tolerant protocol are hazard-free within budget), Regular.v (loops,
product construction, decidability).
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any

from .checker import (Checker, State, _mk_state, apply_effect,
                      guard_satisfiable, initial_state)
from .pack import Pack

BENIGN, FUTILE, CATASTROPHIC = "Benign", "Futile", "Catastrophic"


# --------------------------------------------------------------------------
# Irreversibility: atoms no capability can re-establish
# --------------------------------------------------------------------------

def permanent_deletes(p: Pack) -> dict[str, frozenset]:
    """cap name -> atoms it deletes that NO capability adds back."""
    adds: set[str] = set()
    for c in p.capabilities.values():
        adds |= set(c.add)
    out = {}
    for name, c in p.capabilities.items():
        perm = frozenset(a for a in c.dele if a not in adds)
        if perm:
            out[name] = perm
    return out


def _has_external(steps: list) -> bool:
    for s in steps:
        if "choice" in s:
            if s["choice"].get("external"):
                return True
            for br in s["choice"]["branches"].values():
                if _has_external(br):
                    return True
        if "rec" in s and _has_external(s["rec"]["body"]):
            return True
    return False


# --------------------------------------------------------------------------
# The analysis
# --------------------------------------------------------------------------

@dataclass
class BranchVerdict:
    node: str                     # path to the choice node ("choice@router#0")
    branch: str
    state: tuple                  # sorted true predicates at the node
    severity: str
    intended: bool
    witness: tuple = ()           # path to the hazard if Catastrophic
    pnr_action: str | None = None # the goal-destroying irreversible action


@dataclass
class SeverityReport:
    pack: str
    tolerance_degree: int | None          # None = tolerant at every tested k
    kmax_tested: int
    verdicts: list[BranchVerdict] = field(default_factory=list)
    hazard_witness: tuple = ()            # first hazard within budget k*+1
    pnr_action: str | None = None
    configs_explored: int = 0
    goal_queries: int = 0
    elapsed_s: float = 0.0
    choice_nodes: int = 0
    branches: int = 0
    irreversible_caps: dict = field(default_factory=dict)
    narrowing: list = field(default_factory=list)   # branches to remove
    bystander: dict = field(default_factory=dict)    # Interleave.v check

    def counts(self) -> dict[str, int]:
        c = {BENIGN: 0, FUTILE: 0, CATASTROPHIC: 0}
        for v in self.verdicts:
            c[v.severity] += 1
        return c

    def to_dict(self) -> dict:
        return {
            "pack": self.pack,
            "tolerance_degree": self.tolerance_degree,
            "kmax_tested": self.kmax_tested,
            "counts": self.counts(),
            "choice_nodes": self.choice_nodes,
            "branches": self.branches,
            "irreversible_caps": {k: sorted(v) for k, v in self.irreversible_caps.items()},
            "pnr_action": self.pnr_action,
            "hazard_witness": list(self.hazard_witness),
            "narrowing": self.narrowing,
            "bystander": self.bystander,
            "configs_explored": self.configs_explored,
            "goal_queries": self.goal_queries,
            "elapsed_s": round(self.elapsed_s, 4),
            "verdicts": [
                {"node": v.node, "branch": v.branch, "state": list(v.state),
                 "severity": v.severity, "intended": v.intended,
                 "pnr_action": v.pnr_action, "witness": list(v.witness)}
                for v in self.verdicts],
        }


class SeverityAnalyzer:
    """Budgeted hazard reachability over a pack, with per-branch severity."""

    def __init__(self, pack: Pack, kmax: int = 4,
                 irreversible: list[str] | None = None):
        self.p = pack
        self.kmax = kmax
        self.perm = dict(permanent_deletes(pack))
        # explicit declaration: tools whose real-world effect cannot be undone
        # (send, pay, delete, deploy ...) even if the pack models no delete-list
        for name in (irreversible or getattr(pack, "irreversible", None) or []):
            if name in pack.capabilities:
                self.perm.setdefault(name, frozenset({"<external effect>"}))
        # environment-controlled ("external") choices are resolved demonically:
        # goal reachability must then hold against every environment move
        self.has_external = _has_external(pack.protocol)
        self._chk = Checker(pack, "adversarial" if self.has_external else "may")
        self.goal_queries = 0
        self.configs = 0
        self._goal_memo: dict = {}
        self.verdicts: list[BranchVerdict] = []
        self._seen_verdict: set = set()
        self.choice_nodes: set = set()
        self.branch_count = 0

    # ---- goal reachability (existential, unbudgeted): the checker's search ----
    def goal_reachable(self, steps: list, st: State, recenv: dict) -> bool:
        key = (json.dumps(steps, sort_keys=True), st.true_preds,
               tuple(sorted(recenv)))
        # NOTE: keyed on predicates only -- the widened abstraction the
        # checker itself commits to at loop heads; exact on boolean packs.
        if key in self._goal_memo:
            return self._goal_memo[key]
        self.goal_queries += 1
        self._chk.loop_seen = set()
        self._chk.blocked = []
        ok, _ = self._chk._reach(list(steps), st, dict(recenv))
        self._goal_memo[key] = ok
        return ok

    # ---- budgeted hazard reachability -------------------------------------
    def hazard_within(self, steps: list, st: State, recenv: dict,
                      budget: int, loop_seen: set, node_path: str = "",
                      record: bool = True) -> tuple[bool, tuple, str | None]:
        """(hazard reachable with <= budget misselections, witness, pnr action)."""
        self.configs += 1
        cur = st
        for i, s in enumerate(steps):
            rest = steps[i + 1:]
            if "goal" in s:
                if self._chk._goal_sat(cur):
                    continue                     # marker discharged (G-Goal-F)
                return False, (), None           # unsatisfied marker: stuck
            if "msg" in s:
                cur = _mk_state(cur.true_preds, cur.arith, cur.versions(),
                                cur.path + (("msg", s["msg"]["label"]),))
                continue
            if "spawn" in s:
                return False, (), None           # outside the fragment
            if "act" in s:
                cap = self.p.capabilities.get(s["act"]["cap"])
                if cap is None:
                    return False, (), None       # hallucinated tool: stuck (T-Miss)
                if not guard_satisfiable(cur, cap):
                    return False, (), None       # mandatory act blocked: stuck
                nxt = apply_effect(cur, cap)
                if cap.name in self.perm:
                    # irreversible: catastrophic iff goal unreachable after
                    if not self.goal_reachable(rest, nxt, recenv):
                        return True, nxt.path, cap.name
                cur = nxt
                continue
            if "rec" in s:
                name = s["rec"]["name"]
                unfolding = list(s["rec"]["body"]) + rest
                return self.hazard_within(unfolding, cur, {**recenv, name: unfolding},
                                          budget, loop_seen, node_path, record)
            if "continue" in s:
                name = s["continue"]
                key = (name, cur.true_preds, budget)
                if key in loop_seen:
                    return False, (), None
                loop_seen = loop_seen | {key}
                widened = self._chk._widen(cur, name)
                return self.hazard_within(recenv[name], widened, recenv,
                                          budget, loop_seen, node_path, record)
            if "choice" in s:
                body = s["choice"]
                node = f"{node_path}/choice@{body['by']}#{i}"
                if body.get("external"):
                    # the environment moves: not an agent decision, no budget
                    for label, br in body["branches"].items():
                        bst = _mk_state(cur.true_preds, cur.arith, cur.versions(),
                                        cur.path + (("env", label),))
                        found, wit, pnr = self.hazard_within(
                            list(br) + rest, bst, recenv, budget, loop_seen,
                            f"{node}/{label}", record)
                        if found:
                            return True, wit, pnr
                    return False, (), None
                self.choice_nodes.add(node)
                # when RECORDING, visit every branch even after a hazard was
                # found, so that each branch gets its verdict
                first = None
                for label, br in body["branches"].items():
                    residual = list(br) + rest
                    bst = _mk_state(cur.true_preds, cur.arith, cur.versions(),
                                    cur.path + (("choose", label),))
                    intended = self._intended(body, label, residual, bst, recenv)
                    if intended:
                        found, wit, pnr = self.hazard_within(
                            residual, bst, recenv, budget, loop_seen,
                            f"{node}/{label}", record)
                    elif budget > 0:
                        found, wit, pnr = self.hazard_within(
                            residual, bst, recenv, budget - 1, loop_seen,
                            f"{node}/{label}", record)
                    else:
                        found, wit, pnr = False, (), None
                    if record:
                        self._record(node, label, bst, intended, residual, recenv,
                                     found if not intended else False, wit, pnr)
                    if found:
                        if not record:
                            return True, wit, pnr
                        first = first or (True, wit, pnr)
                return first or (False, (), None)
        return False, (), None

    def _intended(self, body: dict, label: str, residual: list,
                  st: State, recenv: dict) -> bool:
        guards = body.get("guards")
        if guards is not None and label in guards:
            from .checker import eval_formula, _sat
            return _sat(list(st.arith) + [eval_formula(guards[label], st)])
        # default: rational choice -- intended iff the goal survives it
        return self.goal_reachable(residual, st, recenv)

    def _record(self, node, label, st, intended, residual, recenv,
                hazard_found, wit, pnr):
        key = (node, label, st.true_preds)
        if key in self._seen_verdict:
            return
        self._seen_verdict.add(key)
        self.branch_count += 1
        if intended:
            sev = BENIGN
        else:
            # classify the MISSELECTED residual: hazard reachable from it
            # under the remaining budget (as a misselection already spent one)
            found, w2, p2 = self.hazard_within(residual, st, recenv, self.kmax,
                                               set(), node, record=False)
            if found:
                sev, wit, pnr = CATASTROPHIC, w2, p2
            elif self.goal_reachable(residual, st, recenv):
                sev = BENIGN
            else:
                sev = FUTILE
        self.verdicts.append(BranchVerdict(
            node=node, branch=label, state=tuple(sorted(st.true_preds)),
            severity=sev, intended=intended, witness=tuple(wit), pnr_action=pnr))

    # ---- exit interface: (preds, budget-left) at which a segment can END ----
    def exits(self, steps: list, st: State, recenv: dict, budget: int,
              loop_seen: set | None = None) -> tuple[set, bool]:
        """(set of (true_preds, budget_left) terminal configs reachable
        hazard-free, hazard-seen-flag).  Mirrors hazard_within but collects
        every hazard-free termination instead of stopping at the first hazard."""
        loop_seen = loop_seen or set()
        self.configs += 1
        cur = st
        out: set = set()
        for i, s in enumerate(steps):
            rest = steps[i + 1:]
            if "goal" in s:
                if self._chk._goal_sat(cur):
                    continue
                return out, False
            if "msg" in s:
                cur = _mk_state(cur.true_preds, cur.arith, cur.versions(), cur.path)
                continue
            if "spawn" in s:
                return out, False
            if "act" in s:
                cap = self.p.capabilities.get(s["act"]["cap"])
                if cap is None or not guard_satisfiable(cur, cap):
                    return out, False
                nxt = apply_effect(cur, cap)
                if cap.name in self.perm and not self.goal_reachable(rest, nxt, recenv):
                    return out, True
                cur = nxt
                continue
            if "rec" in s:
                name = s["rec"]["name"]
                unfolding = list(s["rec"]["body"]) + rest
                return self.exits(unfolding, cur, {**recenv, name: unfolding}, budget, loop_seen)
            if "continue" in s:
                name = s["continue"]
                key = (name, cur.true_preds, budget)
                if key in loop_seen:
                    return out, False
                return self.exits(recenv[name], self._chk._widen(cur, name), recenv,
                                  budget, loop_seen | {key})
            if "choice" in s:
                body = s["choice"]
                haz = False
                for label, br in body["branches"].items():
                    residual = list(br) + rest
                    bst = _mk_state(cur.true_preds, cur.arith, cur.versions(), cur.path)
                    if body.get("external"):
                        b2 = budget
                    else:
                        intended = self._intended(body, label, residual, bst, recenv)
                        if intended:
                            b2 = budget
                        elif budget > 0:
                            b2 = budget - 1
                        else:
                            continue
                    o, h = self.exits(residual, bst, recenv, b2, loop_seen)
                    out |= o
                    haz = haz or h
                return out, haz
        out.add((cur.true_preds, budget))
        return out, False

    # ---- the report -------------------------------------------------------
    def run(self) -> SeverityReport:
        t0 = time.perf_counter()
        st0 = initial_state(self.p)
        steps = list(self.p.protocol)
        degree: int | None = None
        witness, pnr = (), None
        for k in range(0, self.kmax + 1):
            found, wit, pn = self.hazard_within(steps, st0, {}, k, set(),
                                                record=(k == self.kmax))
            if found:
                degree = k - 1            # tolerant at k-1, not at k
                witness, pnr = wit, pn
                break
        # make sure verdicts are populated even if we broke early
        if not self.verdicts:
            self.hazard_within(steps, st0, {}, self.kmax, set(), record=True)
        rep = SeverityReport(
            pack=self.p.name, tolerance_degree=degree, kmax_tested=self.kmax,
            verdicts=self.verdicts, hazard_witness=witness, pnr_action=pnr,
            configs_explored=self.configs, goal_queries=self.goal_queries,
            elapsed_s=time.perf_counter() - t0,
            choice_nodes=len(self.choice_nodes), branches=self.branch_count,
            irreversible_caps=self.perm)
        rep.narrowing = sorted({(v.node, v.branch) for v in self.verdicts
                                if v.severity == CATASTROPHIC})
        rep.bystander = bystander_conflicts(self.p, self.perm, _atoms_of_formula(self.p.goal))
        return rep


def analyze(pack: dict | Pack, kmax: int = 4,
            irreversible: list[str] | None = None) -> SeverityReport:
    if isinstance(pack, Pack):
        p = pack
    else:
        irreversible = irreversible or pack.get("irreversible")
        p = Pack.load({k: v for k, v in pack.items() if k != "irreversible"})
    return SeverityAnalyzer(p, kmax=kmax, irreversible=irreversible).run()

# ---------------------------------------------------------------------------
# Bystander interleavings (Interleave.v).  The head-move semantics is exact for
# an ungated deployment when every capability action that a bystander could
# fire EARLY is variable-disjoint (STRIPS footprint) from the nodes it would
# pass: `strips_commute`, `strips_enables`, `strips_neutral`,
# `strips_preserves` discharge the semantic side conditions of the swap
# relation.  This function performs that syntactic check and lists the pairs
# the gate must serialize.
# ---------------------------------------------------------------------------
def _atoms_of_formula(f) -> set:
    if f is None:
        return set()
    if isinstance(f, str):
        return {f}
    if isinstance(f, dict):
        out = set()
        for k, v in f.items():
            if k in ("and", "or"):
                for x in v:
                    out |= _atoms_of_formula(x)
            elif k == "not":
                out |= _atoms_of_formula(v)
            else:                       # arithmetic comparison: its variables
                out |= _atoms_of_formula(v) if isinstance(v, (dict, str, list)) else set()
        return out
    if isinstance(f, list):
        out = set()
        for x in f:
            out |= _atoms_of_formula(x)
        return out
    return set()


def bystander_conflicts(p: Pack, perm: frozenset, goal_atoms: set) -> dict:
    caps = p.capabilities
    pre_atoms_all = set()
    for c in caps.values():
        pre_atoms_all |= _atoms_of_formula(getattr(c, "pre", None))
    # support of the derived hazard / rational guards: goal atoms and every
    # precondition atom (goal reachability can depend on nothing else)
    reach_support = set(goal_atoms) | pre_atoms_all

    def eff(name):
        c = caps.get(name)
        if c is None:
            return set()
        return set(c.add or []) | set(c.dele or [])

    def fp(name):
        c = caps.get(name)
        if c is None:
            return set()
        f = eff(name) | _atoms_of_formula(getattr(c, "pre", None))
        if name in perm:
            f |= reach_support        # its hazard bit depends on goal reachability
        return f

    def owner(name):
        c = caps.get(name)
        return getattr(c, "owner", None) if c is not None else None

    pairs, conflicts = 0, []

    def node_roles(node):
        if "act" in node:
            return {owner(node["act"]["cap"])}
        if "msg" in node:
            return {node["msg"].get("from"), node["msg"].get("to")}
        if "choice" in node:
            b = node["choice"]
            return {b.get("by"), b.get("to")} - {None}
        return set()

    def passes(a, r, node) -> str | None:
        """None if a@r may move before `node`; else the reason it may not."""
        nonlocal pairs
        if r in node_roles(node):
            return "own-role"
        if "msg" in node:
            return None
        pairs += 1
        if a in perm:
            return f"{a} is irreversible (not hazard-neutral)"
        if "act" in node:
            b = node["act"]["cap"]
            shared = (eff(a) & fp(b)) | (eff(b) & fp(a))
            return f"shares {sorted(shared)} with {b}" if shared else None
        if "choice" in node:
            body = node["choice"]
            guards = body.get("guards") or {}
            for l, br in body["branches"].items():
                g = guards.get(l)
                sup = _atoms_of_formula(g) if g is not None else reach_support
                shared = eff(a) & sup
                if shared:
                    return f"changes guard support {sorted(shared)} of {l}"
                for inner in reversed(list(br)):
                    why = passes(a, r, inner)
                    if why is not None:
                        return f"branch {l}: {why}"
            return None
        return "loop boundary"

    def walk(steps, prefix):
        for i, s in enumerate(steps):
            if "act" in s:
                a = s["act"]["cap"]; r = owner(a)
                for node in reversed(prefix):
                    why = passes(a, r, node)
                    if why == "own-role":
                        break
                    if why is not None:
                        conflicts.append({"action": f"{a}@{r}", "blocked_at": _node_name(node), "reason": why})
                        break
                prefix = prefix + [s]
            elif "choice" in s:
                for l, br in s["choice"]["branches"].items():
                    walk(list(br), [])
                prefix = prefix + [s]
            elif "rec" in s:
                walk(list(s["rec"]["body"]), [])
                prefix = []
            elif "msg" in s:
                prefix = prefix + [s]
            else:
                prefix = []

    walk(list(p.protocol), [])
    return {"pairs": pairs, "conflicts": conflicts,
            "exact": not conflicts}


def _node_name(node) -> str:
    if "act" in node:
        return "act/" + node["act"]["cap"]
    if "choice" in node:
        return "choice@" + str(node["choice"].get("by"))
    if "msg" in node:
        return "msg/" + str(node["msg"].get("label"))
    return "?"

