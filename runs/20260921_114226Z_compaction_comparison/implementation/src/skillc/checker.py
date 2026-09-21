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
  * INCOMPLETE for achievability (paper, Incompleteness proposition):
    ACHIEVABLE means "structurally admissible", not "guaranteed" -- the
    residue is intent fidelity (top) and payload faithfulness (bottom), owned
    by other layers.

The checker decides an algorithmic form of the paper's achievability judgment
(sections 5.2-5.3): capability soundness, projection-based realizability,
direct conformance of declared role behaviours, and goal may-reachability.
Equivalence between projection and the paper's declarative direct judgment is
an explicit open proof obligation.
Tail-recursive loops (mu X. G) are explored with predicate-state saturation
and numeric widening on the back edge -- widening only enlarges the reachable
set, so refutation stays sound (Coq T2).  Dynamic participant spawning is
outside the decidable fragment (Brand-Zafiropulo): the procedure degrades to
a semi-decision and answers UNKNOWN unless it can refute structurally first.

Verdicts:  ACHIEVABLE (+witness path)  |  IMPOSSIBLE (+reason, +frontier)
           |  UNKNOWN (outside the decidable fragment)
Reasons :  MISSING_CAPABILITY | BLOCKED_GUARD | GOAL_UNSAT | NON_PROJECTABLE
           | NON_CONFORMANT | DYNAMIC_TOPOLOGY

UNKNOWN is an ABSTENTION, not a refutation: it claims nothing in either
direction.  Use Verdict.refuted (not `not achievable`) whenever the question
is "did the checker refute this?" -- the T1 soundness claim is about refuted
verdicts only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import z3

from .formula import CMP, atoms
from .pack import Capability, Pack, normalize, pack_digest
from .session import ProjectionError, conformance_report, participants, project

REASONS = ("OK", "MISSING_CAPABILITY", "BLOCKED_GUARD", "GOAL_UNSAT",
           "NON_PROJECTABLE", "NON_CONFORMANT", "DYNAMIC_TOPOLOGY",
           "PROTOCOL_ONLY", "INCOMPLETE_COMPACTION")

VERDICT_SCHEMA = "skillc.verdict/1"
DEFERRED_OBLIGATIONS = ("intent_fidelity", "payload_faithfulness")

# Every solver query gets a finite budget.  The pack language is QF-LIA
# (validate_expr rejects variable*variable), so queries are decidable in
# principle; the budget is defensive -- a pathological instance degrades to a
# solver UNKNOWN, which _sat resolves toward satisfiable, i.e. away from
# refutation.  A finite budget therefore costs completeness, never soundness.
SOLVER_TIMEOUT_MS = 10_000


def _skillc_version() -> str:
    from . import __version__          # deferred: avoids an import cycle
    return __version__


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
        return z3.Int(f"{var}__init" if v == 0 else f"{var}__{v}")


def _mk_state(preds, arith, version: dict[str, int], path) -> State:
    return State(frozenset(preds), tuple(arith),
                 tuple(sorted(version.items())), tuple(path))


@dataclass(frozen=True)
class TypingState:
    """Symbolic world used to decide the world-sensitive T-Act/T-Goal premises."""

    true_preds: frozenset
    values: tuple

    def env(self) -> dict[str, z3.ArithRef]:
        return dict(self.values)

    def cur(self, var: str) -> z3.ArithRef:
        return self.env().get(var, z3.Int(f"{var}__init"))


def _mk_typing_state(preds, values: dict[str, z3.ArithRef]) -> TypingState:
    return TypingState(frozenset(preds), tuple(sorted(values.items())))


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


def eval_typing_expr(e: Any, st: TypingState) -> z3.ArithRef:
    if isinstance(e, int):
        return z3.IntVal(e)
    if isinstance(e, str):
        return st.cur(e)
    if isinstance(e, dict):
        if "+" in e:
            return (eval_typing_expr(e["+"][0], st)
                    + eval_typing_expr(e["+"][1], st))
        if "-" in e:
            return (eval_typing_expr(e["-"][0], st)
                    - eval_typing_expr(e["-"][1], st))
        if "*" in e:
            return (eval_typing_expr(e["*"][0], st)
                    * eval_typing_expr(e["*"][1], st))
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


def eval_typing_formula(f: Any, st: TypingState) -> z3.BoolRef:
    if f is True:
        return z3.BoolVal(True)
    if f is False:
        return z3.BoolVal(False)
    if isinstance(f, str):
        return z3.BoolVal(f in st.true_preds)
    if isinstance(f, dict):
        if "and" in f:
            return z3.And([eval_typing_formula(x, st) for x in f["and"]])
        if "or" in f:
            return z3.Or([eval_typing_formula(x, st) for x in f["or"]])
        if "not" in f:
            return z3.Not(eval_typing_formula(f["not"], st))
        if "cmp" in f:
            lhs, op, rhs = f["cmp"]
            return CMP[op](eval_typing_expr(lhs, st),
                           eval_typing_expr(rhs, st))
    raise ValueError(f"bad formula: {f!r}")


def _sat(constraints: list, on_unknown: Callable[[], None] | None = None) -> bool:
    """Satisfiability, resolved conservatively toward achievability.

    A solver UNKNOWN (only reachable now by exhausting SOLVER_TIMEOUT_MS,
    since the pack language is linear) counts as satisfiable, so a refutation
    is only ever issued on a definite unsat -- the sound side of the T1
    asymmetry.  `on_unknown` lets the caller record that the answer was an
    approximation rather than a decision."""
    s = z3.Solver()
    s.set("timeout", SOLVER_TIMEOUT_MS)
    s.add(*constraints)
    res = s.check()
    if res == z3.unknown and on_unknown is not None:
        on_unknown()
    return res != z3.unsat


def guard_satisfiable(st: State, cap: Capability,
                      on_unknown: Callable[[], None] | None = None) -> bool:
    return _sat(list(st.arith) + [eval_formula(cap.pre, st)], on_unknown)


def apply_effect(st: State, cap: Capability) -> State:
    new_true = set(st.true_preds)
    for a in cap.add:
        new_true.add(a)
    for d in cap.dele:
        new_true.discard(d)
    old_version = st.versions()
    new_version = dict(old_version)
    new_arith = list(st.arith)
    # deterministic assignments  v := expr  (RHS evaluated in the OLD state)
    for v, expr in cap.assigns.items():
        rhs = eval_expr(expr, st)
        new_version[v] = old_version.get(v, 0) + 1
        new_arith.append(z3.Int(f"{v}__{new_version[v]}") == rhs)
    # Updates are simultaneous.  Each Nd(x) sees old N except for x's new
    # value; Asg takes precedence when both partial maps define the same x.
    for v, constr in cap.nondet.items():
        if v in cap.assigns:
            continue
        new_version[v] = old_version.get(v, 0) + 1
        formula_version = dict(old_version)
        formula_version[v] = new_version[v]
        tmp = _mk_state(st.true_preds, st.arith, formula_version, st.path)
        new_arith.append(eval_formula(constr, tmp))
    return _mk_state(new_true, new_arith, new_version,
                     st.path + (("act", cap.name),))


def initial_state(p: Pack) -> State:
    st0 = _mk_state(p.init_true, (), {}, ())
    cons = [eval_formula(c, st0) for c in p.init_constraints]
    return _mk_state(p.init_true, cons, {}, ())


# --------------------------------------------------------------------------
# Roles and fragment boundary
# --------------------------------------------------------------------------

def roles_acting(steps: list[dict]) -> set[str]:
    """The protocol's participants, `prt(G)`.

    Delegates to the canonical definition in `session.participants` so the
    realizability sweep, the conformance premise and the paper's typing side
    conditions all range over the same set of roles.
    """
    return set(participants(steps))


def has_spawn(steps: list[dict]) -> bool:
    """Dynamic participant spawning: the autonomy boundary (thm:undec)."""
    for s in steps:
        if "spawn" in s:
            return True
        if "choice" in s:
            if any(has_spawn(br) for br in s["choice"]["branches"].values()):
                return True
        if "rec" in s and has_spawn(s["rec"]["body"]):
            return True
    return False


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
    unknown: bool = False        # outside the decidable fragment
    semantics: str = "may"       # judgment the verdict was decided under
    pack_digest: str = ""        # identity of the pack that was decided
    assumed_conformant: tuple = ()   # prt(G) roles with no declared behaviour
    context_refuted: bool = False    # goal impossible over every protocol in Gamma
    decision_scope: str = "protocol"

    @property
    def refutation_scope(self) -> str:
        if not self.refuted:
            return "none"
        return "capability_context" if self.context_refuted else "declared_protocol"

    @property
    def obligations(self) -> tuple:
        """Obligations intentionally outside the static Layer-A verdict."""
        return DEFERRED_OBLIGATIONS if self.label == "ACHIEVABLE" else ()

    @property
    def label(self) -> str:
        if self.unknown:
            return "UNKNOWN"
        return "ACHIEVABLE" if self.achievable else "IMPOSSIBLE"

    @property
    def refuted(self) -> bool:
        """True only for a definite IMPOSSIBLE.

        UNKNOWN means the pack fell outside the decidable fragment, so the
        checker made no claim: it is an abstention.  Counting it as a
        refutation would manufacture false negatives out of honest silence,
        and would misreport the T1 soundness claim, which ranges over
        refutations only."""
        return not self.achievable and not self.unknown

    def to_dict(self) -> dict:
        return {
            "schema": VERDICT_SCHEMA,
            "verdict": self.label,
            "reason": self.reason,
            "detail": self.detail,
            "witness": [list(w) for w in self.witness],
            "frontier": list(self.frontier),
            "achievable": self.achievable,
            "refuted": self.refuted,
            "unknown": self.unknown,
            "semantics": self.semantics,
            "decision_scope": self.decision_scope,
            "refutation_scope": self.refutation_scope,
            "deferred_obligations": list(self.obligations),
            "assumed_conformant": list(self.assumed_conformant),
            "skillc_version": _skillc_version(),
            "pack_digest": self.pack_digest,
        }


def establishable_atoms(p: Pack) -> frozenset:
    """The establisher closure: predicates that can EVER be true -- initially
    true, or added by some capability in Gamma.  Every reachable world of
    every protocol over Gamma stays inside this set (paper: Lemma
    'establisher closure'), because only capability effects change the world
    and Del only shrinks it."""
    out = set(p.init_true)
    for c in p.capabilities.values():
        out |= set(c.add)
    return frozenset(out)


class Checker:
    """The decision procedure over an already-validated Pack.

    check() is the seam that untrusted input goes through: it schema-gates
    dicts and Pack objects alike before constructing a Checker.
    """

    def __init__(self, pack: Pack, semantics: str = "may"):
        if semantics not in ("may", "adversarial"):
            raise ValueError(f"unknown semantics {semantics!r}")
        self.p = pack
        self.semantics = semantics
        self.blocked: list[str] = []     # frontier accumulation
        self.defeated: list[str] = []    # external branches that defeat the goal
        self.loop_seen: set = set()      # (rec name, pred-state) at back edges
        self.solver_unknown = False      # >=1 query hit the solver budget
        self.typing_fresh = 0            # branch-local post-state variables
        self.typing_condition: z3.BoolRef | None = None
        # prt(G) roles the pack declares no behaviour for: the residue of the
        # participant-agreement side condition (see session.ConformanceReport)
        self.assumed_conformant: tuple = ()

    def _note_solver_unknown(self) -> None:
        self.solver_unknown = True

    def run(self) -> Verdict:
        """Decide the pack, then stamp the verdict with what decided it."""
        v = self._decide()
        v.semantics = self.semantics
        v.assumed_conformant = self.assumed_conformant
        if self.solver_unknown:
            note = (f"solver returned unknown on at least one query "
                    f"(budget {SOLVER_TIMEOUT_MS} ms); resolved toward "
                    f"satisfiable, so no refutation rests on it")
            v.detail = f"{v.detail} [{note}]" if v.detail else note
        return v

    def _gamma_refutation(self, guard_closure: bool = False) -> Verdict | None:
        """Protocol-independent refutation over the establisher closure.

        Encode the goal with every non-establishable atom pinned FALSE and
        everything else (establishable atoms, arithmetic comparisons) left
        FREE.  If that over-approximation is unsatisfiable, no run of ANY
        protocol over Gamma -- including protocols that spawn participants,
        who still act through Gamma -- can satisfy the goal.  This is the
        FlightInstance argument made general and checked by z3.
        """
        can = set(self.p.init_true) if guard_closure else establishable_atoms(self.p)
        fresh = iter(range(10 ** 9))

        def enc(f: Any) -> z3.BoolRef:
            if f is True:
                return z3.BoolVal(True)
            if f is False:
                return z3.BoolVal(False)
            if isinstance(f, str):
                return z3.Bool(f"__predicate_{f}") if f in can else z3.BoolVal(False)
            if "and" in f:
                return z3.And([enc(x) for x in f["and"]])
            if "or" in f:
                return z3.Or([enc(x) for x in f["or"]])
            if "not" in f:
                return z3.Not(enc(f["not"]))
            if "cmp" in f:
                return z3.Bool(f"__cmp_{next(fresh)}")   # arithmetic left free
            raise ValueError(f"bad formula: {f!r}")

        if guard_closure:
            remaining = list(self.p.capabilities.values())
            while remaining:
                enabled = [
                    cap for cap in remaining
                    if _sat([enc(cap.pre)], self._note_solver_unknown)]
                if not enabled:
                    break
                for cap in enabled:
                    can.update(cap.add)
                    remaining.remove(cap)
        if _sat([enc(self.p.goal)], self._note_solver_unknown):
            return None
        dead = tuple(sorted(atoms(self.p.goal) - can))
        return Verdict(False, "GOAL_UNSAT",
                       f"protocol-independent refutation: "
                       f"{'guard-reachable capabilities' if guard_closure else 'capabilities'} "
                       f"in Gamma cannot establish {list(dead)} and the goal cannot "
                       f"hold without them -- every protocol over these "
                       f"capabilities is doomed, spawning included",
                       frontier=dead, context_refuted=True)

    def _decide(self) -> Verdict:
        # 1. capability existence (no hallucinated tools).  This premise is
        #    decided first and survives autonomy: a tool absent from Gamma
        #    stays absent no matter how many participants are spawned.
        missing = self._missing_caps(self.p.protocol)
        if missing:
            goal_refutation = self._gamma_refutation()
            return Verdict(False, "MISSING_CAPABILITY",
                           f"protocol invokes undeclared capabilities: {sorted(missing)}",
                           frontier=tuple(sorted(missing)),
                           context_refuted=goal_refutation is not None)
        # 1b. establisher-closure refutation: protocol-independent, so it too
        #     survives autonomy and is decided before degrading to UNKNOWN.
        gamma = self._gamma_refutation()
        if gamma:
            return gamma
        # 2. the autonomy boundary: dynamic spawning -> unbounded participants
        #    -> undecidable (thm:undec).  Degrade to a semi-decision.
        if has_spawn(self.p.protocol):
            return Verdict(False, "DYNAMIC_TOPOLOGY",
                           "protocol spawns participants at run time; "
                           "achievability is undecidable outside the "
                           "static-topology fragment (Brand-Zafiropulo)",
                           unknown=True)
        # 3. realizability: projection G|p defined for every role (Proj-Sel /
        #    Proj-Brn / Proj-Mrg).  Undefined = deadlocking handoff.
        for role in sorted(set(self.p.roles) | roles_acting(self.p.protocol)):
            try:
                project(self.p.protocol, role)
            except ProjectionError as e:
                return Verdict(False, "NON_PROJECTABLE", str(e))
        # 4. conformance: every declared skill refines its projected contract
        #    (S_p <= G|p, Gay-Hole subtyping).  Refutes the *judgment*: the
        #    verdict on G cannot be transported to a non-conforming skill.
        rep = conformance_report(self.p.skills, self.p.protocol)
        if not rep.ok:
            return Verdict(False, "NON_CONFORMANT", rep.failure)
        self.assumed_conformant = rep.assumed
        # T-Comm quantifies over every protocol branch at the same pre-world;
        # T-Act and T-Goal then check guards/markers in lockstep.  Projection
        # alone only checks process shape, so decide these world premises too.
        typing_condition = self._direct_typing_condition()
        # 5. tolerant may-reachability of the goal
        ok, end_state = self._reach(self.p.protocol, initial_state(self.p), {})
        if ok:
            # Search again with the shared-world premise at each goal.
            # Rejecting only the first witness would miss compatible later
            # branches; omitting the goal would admit incompatible worlds.
            self.typing_condition = typing_condition
            self.loop_seen.clear()
            self.blocked.clear()
            self.defeated.clear()
            ok, end_state = self._reach(
                self.p.protocol, initial_state(self.p), {})
            if not ok:
                return Verdict(
                    False, "NON_CONFORMANT",
                    "a may-reachability witness exists, but the whole-session "
                    "T-Comm/T-Act/T-Goal judgment has no derivation from the "
                    "same initial world: the protocol-wide guards and goal "
                    "markers are inconsistent with the witness")
            return Verdict(True, "OK", "goal reachable along witness path",
                           witness=end_state.path)
        if self.defeated:
            uniq = tuple(dict.fromkeys(self.defeated))
            return Verdict(False, "GOAL_UNSAT",
                           "adversarially unachievable: " + "; ".join(uniq),
                           frontier=uniq)
        if self.blocked:
            uniq = tuple(dict.fromkeys(self.blocked))
            return Verdict(False, "BLOCKED_GUARD", "; ".join(uniq), frontier=uniq)
        return Verdict(False, "GOAL_UNSAT",
                       "protocol terminates but no run satisfies the goal "
                       "(goal predicate never established / refinement unsatisfiable)")

    def _fresh_typing_value(self, var: str) -> z3.ArithRef:
        self.typing_fresh += 1
        return z3.Int(f"{var}__typing_{self.typing_fresh}")

    def _typing_effect(self, st: TypingState,
                       cap: Capability) -> tuple[TypingState, list[z3.BoolRef]]:
        preds = set(st.true_preds) | set(cap.add)
        preds -= set(cap.dele)
        old = st.env()
        values = dict(old)
        constraints: list[z3.BoolRef] = []
        for var, expr in cap.assigns.items():
            values[var] = eval_typing_expr(expr, st)
        for var, formula in cap.nondet.items():
            if var in cap.assigns:
                continue
            fresh = self._fresh_typing_value(var)
            formula_values = dict(old)
            formula_values[var] = fresh
            formula_state = _mk_typing_state(st.true_preds, formula_values)
            constraints.append(eval_typing_formula(formula, formula_state))
            values[var] = fresh
        return _mk_typing_state(preds, values), constraints

    def _typing_condition(self, steps: list[dict], st: TypingState,
                          recenv: dict[str, list[dict]],
                          seen: frozenset) -> z3.BoolRef:
        if not steps:
            return z3.BoolVal(True)
        step, rest = steps[0], steps[1:]
        if "goal" in step:
            return z3.And(
                eval_typing_formula(step["goal"], st),
                self._typing_condition(rest, st, recenv, seen))
        if "msg" in step:
            return self._typing_condition(rest, st, recenv, seen)
        if "act" in step:
            cap = self.p.capabilities[step["act"]["cap"]]
            post, effect_constraints = self._typing_effect(st, cap)
            return z3.And(
                eval_typing_formula(cap.pre, st),
                *effect_constraints,
                self._typing_condition(rest, post, recenv, seen))
        if "choice" in step:
            return z3.And([
                self._typing_condition(list(branch) + rest, st, recenv,
                                       frozenset(seen))
                for branch in step["choice"]["branches"].values()
            ])
        if "rec" in step:
            name = step["rec"]["name"]
            unfolding = list(step["rec"]["body"]) + rest
            return self._typing_condition(
                unfolding, st, {**recenv, name: unfolding}, seen)
        if "continue" in step:
            name = step["continue"]
            key = (name, st.true_preds)
            if key in seen:
                # Coinductive closure after predicate-state saturation.  This
                # is an over-approximation for numeric loops, so it can only
                # withhold a conformance refutation, never create one.
                return z3.BoolVal(True)
            return self._typing_condition(
                recenv[name], st, recenv, seen | {key})
        raise ValueError(f"unsupported typing step: {step!r}")

    def _direct_typing_condition(self) -> z3.BoolRef:
        st = _mk_typing_state(self.p.init_true, {})
        initial = [eval_typing_formula(f, st)
                   for f in self.p.init_constraints]
        condition = self._typing_condition(
            self.p.protocol, st, {}, frozenset())
        return z3.And(*initial, condition)

    def _missing_caps(self, steps: list[dict]) -> set[str]:
        out: set[str] = set()
        for s in steps:
            if "act" in s and s["act"]["cap"] not in self.p.capabilities:
                out.add(s["act"]["cap"])
            if "choice" in s:
                for br in s["choice"]["branches"].values():
                    out |= self._missing_caps(br)
            if "rec" in s:
                out |= self._missing_caps(s["rec"]["body"])
        return out

    def _goal_sat(self, st: State) -> bool:
        constraints = list(st.arith) + [eval_formula(self.p.goal, st)]
        if self.typing_condition is not None:
            constraints.append(self.typing_condition)
        return _sat(constraints, self._note_solver_unknown)

    def _widen(self, st: State, label: str) -> State:
        """Back-edge widening: havoc the numeric summary.  Dropping the
        accumulated arithmetic constraints only ENLARGES the reachable set,
        so refutation remains sound (Coq T2); together with the finite
        predicate valuations it makes the loop search terminate (thm:dec)."""
        bumped = {v: n + 1 for v, n in st.versions().items()}
        return _mk_state(st.true_preds, (), bumped,
                         st.path + (("continue", label),))

    def _reach(self, steps: list[dict], st: State,
               recenv: dict) -> tuple[bool, State]:
        """(reached_goal, witnessing/end state).  Existential over branches."""
        cur = st
        for i, s in enumerate(steps):
            if "goal" in s:                        # explicit goal marker
                if self._goal_sat(cur):
                    return True, cur
                return False, cur                   # unsatisfied checkpoint
            elif "msg" in s:
                cur = _mk_state(cur.true_preds, cur.arith, cur.versions(),
                                cur.path + (("msg", s["msg"]["label"]),))
            elif "act" in s:
                cap = self.p.capabilities[s["act"]["cap"]]
                guard = eval_formula(cap.pre, cur)
                if not _sat(list(cur.arith) + [guard],
                            self._note_solver_unknown):
                    self.blocked.append(
                        f"capability '{cap.name}' guard never satisfiable on "
                        f"this path (pre={cap.pre!r})")
                    return False, cur              # mandatory action blocked
                guarded = _mk_state(
                    cur.true_preds, list(cur.arith) + [guard],
                    cur.versions(), cur.path)
                successor = apply_effect(guarded, cap)
                if not _sat(list(successor.arith), self._note_solver_unknown):
                    self.blocked.append(
                        f"capability '{cap.name}' has no successor world "
                        f"satisfying its nondeterministic effect")
                    return False, cur
                cur = successor
            elif "rec" in s:
                # mu X. body : the fall-through continuation folds into the
                # unfolding (tail recursion), so the remainder is consumed
                name = s["rec"]["name"]
                unfolding = list(s["rec"]["body"]) + steps[i + 1:]
                return self._reach(unfolding, cur,
                                   {**recenv, name: unfolding})
            elif "continue" in s:
                name = s["continue"]
                key = (name, cur.true_preds)
                if key in self.loop_seen:
                    # same abstract configuration already explored: with the
                    # numerics widened, further unfolding adds nothing new
                    return False, cur
                self.loop_seen.add(key)
                return self._reach(recenv[name], self._widen(cur, name), recenv)
            elif "choice" in s:
                rest = steps[i + 1:]
                body = s["choice"]
                demonic = (self.semantics == "adversarial"
                           and body.get("external", False))
                last_end = cur
                for label, br in body["branches"].items():
                    branch_state = _mk_state(cur.true_preds, cur.arith,
                                             cur.versions(),
                                             cur.path + (("choose", label),))
                    ok, end = self._reach(list(br) + rest, branch_state, recenv)
                    if demonic:
                        # universal: the environment resolves this choice, so
                        # EVERY branch must still reach the goal
                        if not ok:
                            self.defeated.append(
                                f"external branch '{label}' of the choice by "
                                f"'{body['by']}' defeats the goal")
                            return False, end
                        last_end = end
                    elif ok:
                        # existential: ANY branch + continuation suffices
                        return True, end
                return (True, last_end) if demonic else (False, cur)
        # end of this block: check goal at terminal
        if self._goal_sat(cur):
            return True, cur
        return False, cur


def check(pack: dict | Pack, semantics: str = "may",
          scope: str = "protocol") -> Verdict:
    """Check a pack (dict or Pack) and return the Verdict.

    Both input shapes go through the same schema gate (pack.normalize ->
    validate_pack): a Pack assembled in memory is untrusted input too, and a
    malformed one raises PackError rather than reaching the trusted core.
    The verdict carries the identity of what was decided (pack_digest) and
    the judgment it was decided under (semantics).

    semantics="may"          angelic ◇: some resolution of every choice works
                             (the paper's Layer-A judgment; refutation sound).
    semantics="adversarial"  choices marked {"external": true} are resolved by
                             the environment: the goal must be reachable under
                             EVERY resolution of external choices, while the
                             agent's own choices stay existential (AND-OR
                             search).  ACHIEVABLE then means the agent has a
                             winning strategy against the declared model.

    scope="protocol"        the default judgment about the declared protocol.
    scope="goal"            may-only selective judgment: refute only with a
                             capability-context certificate; otherwise abstain
                             on protocol rejection. The guard closure ignores
                             deletes and treats numeric comparisons as free
                             Booleans, over-approximating possible producers.
    """
    if scope not in {"protocol", "goal"}:
        raise ValueError(f"unknown decision scope: {scope!r}")
    if scope == "goal" and semantics != "may":
        raise ValueError("goal scope supports may semantics only")
    p = normalize(pack)
    checker = Checker(p, semantics=semantics)
    certificate = checker._gamma_refutation(guard_closure=True) if scope == "goal" else None
    v = certificate if certificate is not None else checker.run()
    v.decision_scope = scope
    if scope == "goal" and v.refuted and not v.context_refuted:
        protocol_reason = v.reason
        v.unknown = True
        v.reason = "PROTOCOL_ONLY"
        v.detail = (
            f"declared protocol rejected ({protocol_reason}), but no "
            f"protocol-independent goal refutation was established; "
            f"alternative plans are not ruled out. {v.detail}")
    v.pack_digest = pack_digest(p)
    return v
