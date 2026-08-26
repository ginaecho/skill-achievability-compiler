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
from .session import ProjectionError, conformance_failure, project

REASONS = ("OK", "MISSING_CAPABILITY", "BLOCKED_GUARD", "GOAL_UNSAT",
           "NON_PROJECTABLE", "NON_CONFORMANT", "DYNAMIC_TOPOLOGY")

VERDICT_SCHEMA = "skillc.verdict/1"

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
# Roles and fragment boundary
# --------------------------------------------------------------------------

def roles_acting(steps: list[dict]) -> set[str]:
    out: set[str] = set()
    for s in steps:
        if "act" in s:
            out.add(s["act"].get("by", "?"))
        if "msg" in s:
            out.add(s["msg"]["from"])
            out.add(s["msg"]["to"])
        if "choice" in s:
            out.add(s["choice"]["by"])
            for br in s["choice"]["branches"].values():
                out |= roles_acting(br)
        if "rec" in s:
            out |= roles_acting(s["rec"]["body"])
    return out


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

    def _note_solver_unknown(self) -> None:
        self.solver_unknown = True

    def run(self) -> Verdict:
        """Decide the pack, then stamp the verdict with what decided it."""
        v = self._decide()
        v.semantics = self.semantics
        if self.solver_unknown:
            note = (f"solver returned unknown on at least one query "
                    f"(budget {SOLVER_TIMEOUT_MS} ms); resolved toward "
                    f"satisfiable, so no refutation rests on it")
            v.detail = f"{v.detail} [{note}]" if v.detail else note
        return v

    def _gamma_refutation(self) -> Verdict | None:
        """Protocol-independent refutation over the establisher closure.

        Encode the goal with every non-establishable atom pinned FALSE and
        everything else (establishable atoms, arithmetic comparisons) left
        FREE.  If that over-approximation is unsatisfiable, no run of ANY
        protocol over Gamma -- including protocols that spawn participants,
        who still act through Gamma -- can satisfy the goal.  This is the
        FlightInstance argument made general and checked by z3.
        """
        can = establishable_atoms(self.p)
        fresh = iter(range(10 ** 9))

        def enc(f: Any) -> z3.BoolRef:
            if f is True:
                return z3.BoolVal(True)
            if f is False:
                return z3.BoolVal(False)
            if isinstance(f, str):
                return z3.Bool(f) if f in can else z3.BoolVal(False)
            if "and" in f:
                return z3.And([enc(x) for x in f["and"]])
            if "or" in f:
                return z3.Or([enc(x) for x in f["or"]])
            if "not" in f:
                return z3.Not(enc(f["not"]))
            if "cmp" in f:
                return z3.Bool(f"__cmp_{next(fresh)}")   # arithmetic left free
            raise ValueError(f"bad formula: {f!r}")

        if _sat([enc(self.p.goal)], self._note_solver_unknown):
            return None
        dead = tuple(sorted(atoms(self.p.goal) - can))
        return Verdict(False, "GOAL_UNSAT",
                       f"protocol-independent refutation: no capability in "
                       f"Gamma establishes {list(dead)} and the goal cannot "
                       f"hold without them -- every protocol over these "
                       f"capabilities is doomed, spawning included",
                       frontier=dead)

    def _decide(self) -> Verdict:
        # 1. capability existence (no hallucinated tools).  This premise is
        #    decided first and survives autonomy: a tool absent from Gamma
        #    stays absent no matter how many participants are spawned.
        missing = self._missing_caps(self.p.protocol)
        if missing:
            return Verdict(False, "MISSING_CAPABILITY",
                           f"protocol invokes undeclared capabilities: {sorted(missing)}",
                           frontier=tuple(sorted(missing)))
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
        if self.p.skills:
            fail = conformance_failure(self.p.skills, self.p.protocol)
            if fail:
                return Verdict(False, "NON_CONFORMANT", fail)
        # 5. tolerant may-reachability of the goal
        ok, end_state = self._reach(self.p.protocol, initial_state(self.p), {})
        if ok:
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
        return _sat(list(st.arith) + [eval_formula(self.p.goal, st)],
                    self._note_solver_unknown)

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
                if not guard_satisfiable(cur, cap, self._note_solver_unknown):
                    self.blocked.append(
                        f"capability '{cap.name}' guard never satisfiable on "
                        f"this path (pre={cap.pre!r})")
                    return False, cur              # mandatory action blocked
                cur = apply_effect(cur, cap)
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


def check(pack: dict | Pack, semantics: str = "may") -> Verdict:
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
    """
    p = normalize(pack)
    v = Checker(p, semantics=semantics).run()
    v.pack_digest = pack_digest(p)
    return v
