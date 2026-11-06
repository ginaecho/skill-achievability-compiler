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

A verdict has two orthogonal dimensions (verdict schema skillc.verdict/2):

  Goal (label)   ACHIEVABLE (+witness path)  |  IMPOSSIBLE (+reason, +frontier)
                 |  UNKNOWN (abstention)
    IMPOSSIBLE reasons: MISSING_CAPABILITY | BLOCKED_GUARD | GOAL_UNSAT
    UNKNOWN reasons   : DYNAMIC_TOPOLOGY | PROTOCOL_ONLY (goal scope)
                        | INCOMPLETE_COMPACTION (front-end)
  Protocol       WELL_TYPED | REJECTED (+protocol_reason) | NOT_CHECKED
    protocol reasons  : NON_PROJECTABLE | NON_CONFORMANT | MISSING_CAPABILITY

A tool the protocol names but Gamma lacks is a goal refutation
(IMPOSSIBLE / MISSING_CAPABILITY) only when every path to a goal point uses
such a tool.  When some path avoids every missing tool, the goal is still
decided by the search, which treats each step with a missing tool as a dead
end (World-Act cannot fire it), and the missing tool is recorded as a
protocol rejection (protocol_reason MISSING_CAPABILITY): the typing premise
caps(G) <= dom(Gamma) of rule Ach fails, which is not goal impossibility.

Only the goal dimension is covered by the refutation soundness result
(Theorem 1 + Lemma 3, proof/SkillAchievability.v).  A protocol rejection is
a typing failure: T-Comm requires EVERY branch to conform, so one bad branch
rejects the protocol even when another branch reaches the goal.  A protocol
rejection therefore never establishes that the goal is unreachable, and it is
never folded into IMPOSSIBLE.  Deployment gates and runtime monitors must
allow only Verdict.admissible (ACHIEVABLE and not REJECTED).

UNKNOWN is an ABSTENTION, not a refutation: it claims nothing in either
direction.  Use Verdict.refuted (not `not achievable`) whenever the question
is "did the checker refute this?" -- the T1 soundness claim is about refuted
verdicts only.  Verdict.coverage names the formal result behind each goal
verdict; see docs/VERDICT_COVERAGE.md.

Branch assumptions (a choice's `assumes`): entering branch L of a choice adds
the predicates `assumes[L]` to the world before the branch body, exactly like
an `add` effect, under both semantics and in the whole-session typing
judgment; the establisher closure includes them.  The assumed facts are
declared by the pack itself, so Theorem 1's soundness relative to the declared
pack is unchanged: the pack's world now has one more kind of declared
establisher, and a refutation still ranges over exactly what the pack declares.
"""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

import z3

from .formula import CMP, atoms, compile_expr, compile_formula
from .pack import Capability, Pack, assumed_atoms, iter_steps, normalize, pack_digest
from .session import ProjectionError, conformance_report, participants, project

# NON_PROJECTABLE / NON_CONFORMANT stay listed so that consumers of schema
# v1 still parse them; since v2 they appear only as protocol_reason values.
REASONS = ("OK", "MISSING_CAPABILITY", "BLOCKED_GUARD", "GOAL_UNSAT",
           "NON_PROJECTABLE", "NON_CONFORMANT", "DYNAMIC_TOPOLOGY",
           "PROTOCOL_ONLY", "INCOMPLETE_COMPACTION", "REQUIREMENT_UNAVAILABLE")
PROTOCOL_STATUSES = ("WELL_TYPED", "REJECTED", "NOT_CHECKED")
PROTOCOL_REASONS = ("", "NON_PROJECTABLE", "NON_CONFORMANT", "MISSING_CAPABILITY")
# reasons whose IMPOSSIBLE verdict is a may-reachability refutation (thm1)
_REACHABILITY_REASONS = ("MISSING_CAPABILITY", "BLOCKED_GUARD", "GOAL_UNSAT")
PROTOCOL_COVERAGE = "t-comm:side-conditions;sr+sf:single-label-mechanized"

VERDICT_SCHEMA = "skillc.verdict/2"
DEFERRED_OBLIGATIONS = ("intent_fidelity", "payload_faithfulness")

# Every solver query gets a finite budget.  The pack language is QF-LIA
# (validate_expr rejects variable*variable), so queries are decidable in
# principle; the budget is defensive -- a pathological instance degrades to a
# solver UNKNOWN, which _sat resolves toward satisfiable, i.e. away from
# refutation.  A finite budget therefore costs completeness, never soundness.
SOLVER_TIMEOUT_MS = 10_000
_TRACE_OBSERVER: ContextVar[Callable[[str, dict], None] | None] = ContextVar(
    "skillc_trace_observer",
    default=None,
)


@contextmanager
def observe_check(observer: Callable[[str, dict], None]):
    """Observe trusted-check stage artifacts without changing checker results."""
    token = _TRACE_OBSERVER.set(observer)
    try:
        yield
    finally:
        _TRACE_OBSERVER.reset(token)


def trace_artifact(stage: str, payload: dict) -> None:
    observer = _TRACE_OBSERVER.get()
    if observer is not None:
        observer(stage, payload)


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


def eval_expr(e: Any, st: State | TypingState) -> z3.ArithRef:
    return compile_expr(e, st.cur)


def eval_formula(f: Any, st: State | TypingState) -> z3.BoolRef:
    """Compile a formula against concrete predicate truth + symbolic numerics."""
    return compile_formula(
        f,
        pred=lambda name: z3.BoolVal(name in st.true_preds),
        cmp=lambda lhs, op, rhs: CMP[op](eval_expr(lhs, st), eval_expr(rhs, st)))


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
    return any("spawn" in s for s in iter_steps(steps))


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
    # The protocol-typing dimension, orthogonal to the goal label above.
    protocol: str = "WELL_TYPED"     # WELL_TYPED | REJECTED | NOT_CHECKED
    protocol_reason: str = ""        # "" | NON_PROJECTABLE | NON_CONFORMANT | MISSING_CAPABILITY
    protocol_detail: str = ""

    @property
    def admissible(self) -> bool:
        """What a deployment gate or runtime monitor must use to ALLOW:
        the goal is reachable along a witness AND the protocol is not
        rejected.  ACHIEVABLE alone is not enough."""
        return self.achievable and not self.unknown and self.protocol != "REJECTED"

    @property
    def coverage(self) -> str:
        """Which formal result covers the GOAL verdict (machine-readable).

        thm1+lem3            Theorem 1 (refutation_sound_rel) + Lemma 3
                             (SymbolicInstance.symbolic_refutation_sound),
                             both mechanized; the QF-LIA denotation and the
                             SMT solver are trusted.
        +establisher         the refutation also holds over every protocol
                             in Gamma (establisher-closure lemma, paper-only).
        paper-only:adversarial  refutation under adversarial semantics.
        thm-undec:abstention    abstention at the undecidable boundary.
        abstention           any other abstention.
        none:witness-only    ACHIEVABLE: a witness exists; not a guarantee
                             (incompleteness proposition).
        deterministic-reader:manifest  REQUIREMENT_UNAVAILABLE: the
                             requirement reader (`env.manifest`) found a hard
                             requirement the runtime manifest marks
                             unavailable; not covered by Theorem 1.
        """
        if self.unknown:
            return ("thm-undec:abstention" if self.reason == "DYNAMIC_TOPOLOGY"
                    else "abstention")
        if self.achievable:
            return "none:witness-only"
        if self.reason == "REQUIREMENT_UNAVAILABLE":
            return "deterministic-reader:manifest"
        if self.semantics == "adversarial":
            return "paper-only:adversarial"
        if self.reason in _REACHABILITY_REASONS:
            return "thm1+lem3+establisher" if self.context_refuted else "thm1+lem3"
        return "none"

    @property
    def protocol_coverage(self) -> str:
        """Which formal result covers the protocol-typing result.

        Protocol typing results never establish goal impossibility: a
        REJECTED protocol may still reach the goal along some branch, and a
        WELL_TYPED protocol says nothing about the goal by itself."""
        if self.protocol in ("REJECTED", "WELL_TYPED"):
            return PROTOCOL_COVERAGE
        return "not-checked"

    @property
    def refutation_scope(self) -> str:
        if not self.refuted:
            return "none"
        if self.reason == "REQUIREMENT_UNAVAILABLE":
            return "runtime_manifest"
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
            "protocol": self.protocol,
            "protocol_reason": self.protocol_reason,
            "protocol_detail": self.protocol_detail,
            "admissible": self.admissible,
            "coverage": self.coverage,
            "protocol_coverage": self.protocol_coverage,
            "deferred_obligations": list(self.obligations),
            "assumed_conformant": list(self.assumed_conformant),
            "skillc_version": _skillc_version(),
            "pack_digest": self.pack_digest,
        }


def establishable_atoms(p: Pack) -> frozenset:
    """The establisher closure: predicates that can EVER be true -- initially
    true, added by some capability in Gamma, or assumed by some choice branch
    of the protocol.  Every reachable world of every protocol over Gamma stays
    inside this set (paper: Lemma 'establisher closure'), because only
    capability effects and declared branch assumptions change the world and
    Del only shrinks it.  (Assumed facts are declared by the pack, so the
    closure is still relative to the pack.)"""
    out = set(p.init_true) | assumed_atoms(p.protocol)
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
        self.missing: set[str] = set()   # tools the protocol names but Gamma lacks
        self.missing_hit: set[str] = set()  # missing tools the search ran into
        self.solver_unknown = False      # >=1 query hit the solver budget
        self.typing_fresh = 0            # branch-local post-state variables
        self.typing_condition: z3.BoolRef | None = None
        # prt(G) roles the pack declares no behaviour for: the residue of the
        # participant-agreement side condition (see session.ConformanceReport)
        self.assumed_conformant: tuple = ()
        # protocol-typing dimension, recorded by _decide and stamped by run()
        self.protocol_status = "NOT_CHECKED"
        self.protocol_reason = ""
        self.protocol_detail = ""

    def _reject_protocol(self, reason: str, detail: str) -> None:
        """Record the FIRST protocol-typing failure; later ones are ignored."""
        if self.protocol_status == "REJECTED":
            return
        self.protocol_status = "REJECTED"
        self.protocol_reason = reason
        self.protocol_detail = detail

    def _note_solver_unknown(self) -> None:
        self.solver_unknown = True

    def _sat(self, constraints: list) -> bool:
        return _sat(constraints, self._note_solver_unknown)

    def run(self) -> Verdict:
        """Decide the pack, then stamp the verdict with what decided it."""
        v = self._decide()
        v.semantics = self.semantics
        v.assumed_conformant = self.assumed_conformant
        v.protocol = self.protocol_status
        v.protocol_reason = self.protocol_reason
        v.protocol_detail = self.protocol_detail
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
        # branch assumptions are declared establishers too (see establishable_atoms)
        can = (set(self.p.init_true) | assumed_atoms(self.p.protocol)
               if guard_closure else establishable_atoms(self.p))
        fresh = iter(range(10 ** 9))

        def enc(f: Any) -> z3.BoolRef:
            return compile_formula(
                f,
                # non-establishable atoms are pinned FALSE, the rest left free
                pred=lambda name: (z3.Bool(f"__predicate_{name}") if name in can
                                   else z3.BoolVal(False)),
                # arithmetic left free
                cmp=lambda *_: z3.Bool(f"__cmp_{next(fresh)}"))

        if guard_closure:
            remaining = list(self.p.capabilities.values())
            while remaining:
                enabled = [cap for cap in remaining
                           if self._sat([enc(cap.pre)])]
                if not enabled:
                    break
                for cap in enabled:
                    can.update(cap.add)
                    remaining.remove(cap)
        if self._sat([enc(self.p.goal)]):
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
        required = sorted(
            {step["act"]["cap"] for step in iter_steps(self.p.protocol)
             if "act" in step}
        )
        trace_artifact("capability", {
            "status": "refuted" if missing else "passed",
            "required_by_protocol": required,
            "available_definitions": sorted(self.p.capabilities),
            "missing": sorted(missing),
        })
        if missing and not self._avoids_missing(self.p.protocol, missing, {}):
            # every path to a goal point fires a tool Gamma lacks, and
            # World-Act cannot fire it: no run reaches the goal (thm1).
            goal_refutation = self._gamma_refutation()
            self._skip_traces(
                "capability existence failed",
                interaction=True,
                reachability=True,
            )
            return Verdict(False, "MISSING_CAPABILITY",
                           f"protocol invokes undeclared capabilities: {sorted(missing)}",
                           frontier=tuple(sorted(missing)),
                           context_refuted=goal_refutation is not None)
        if missing and (goal_refutation := self._gamma_refutation()):
            # a path avoids the missing tools, but no protocol over Gamma can
            # reach the goal at all: report the missing tool, the actionable
            # cause, with the protocol-independent certificate behind it.
            self._skip_traces(
                "capability existence failed",
                interaction=True,
                reachability=True,
            )
            return Verdict(False, "MISSING_CAPABILITY",
                           f"protocol invokes undeclared capabilities: {sorted(missing)}; "
                           f"{goal_refutation.detail}",
                           frontier=tuple(sorted(missing)),
                           context_refuted=True)
        if missing:
            # Some path avoids every missing tool, so the goal is decided by
            # the search below.  The failed premise caps(G) <= dom(Gamma) is
            # a typing failure, recorded in the protocol dimension.
            self.missing = missing
            self._reject_protocol(
                "MISSING_CAPABILITY",
                f"protocol invokes undeclared capabilities {sorted(missing)} "
                f"on a path the goal does not need; an agent that takes that "
                f"path cannot complete it")
        # 1b. establisher-closure refutation: protocol-independent, so it too
        #     survives autonomy and is decided before degrading to UNKNOWN.
        gamma = self._gamma_refutation()
        if gamma:
            self._skip_traces(
                "capability context already refutes the goal",
                interaction=True,
                reachability=True,
            )
            return gamma
        # 2. the autonomy boundary: dynamic spawning -> unbounded participants
        #    -> undecidable (thm:undec).  Degrade to a semi-decision.
        if has_spawn(self.p.protocol):
            trace_artifact("interaction", {
                "status": "unknown",
                "reason": "dynamic participant spawning is outside the decidable fragment",
            })
            self._skip_traces(
                "dynamic topology prevents finite interaction and reachability checks",
                reachability=True,
            )
            return Verdict(False, "DYNAMIC_TOPOLOGY",
                           "protocol spawns participants at run time; "
                           "achievability is undecidable outside the "
                           "static-topology fragment (Brand-Zafiropulo)",
                           unknown=True)
        # From here on the protocol-typing dimension is decided alongside,
        # and independently of, goal reachability.  A typing failure is
        # recorded, never returned: T-Comm requires every branch to conform,
        # so one bad branch rejects the protocol even when another branch
        # reaches the goal -- it is not a goal refutation (Theorem 1 covers
        # reachability refutations only).
        if self.protocol_status != "REJECTED":
            self.protocol_status = "WELL_TYPED"
        # 3. realizability: projection G|p defined for every role (Proj-Sel /
        #    Proj-Brn / Proj-Mrg).  Undefined = deadlocking handoff.
        projections = {}
        for role in sorted(set(self.p.roles) | roles_acting(self.p.protocol)):
            try:
                projections[role] = _jsonable(project(self.p.protocol, role))
            except ProjectionError as e:
                trace_artifact("interaction", {
                    "status": "rejected",
                    "check": "projection",
                    "role": role,
                    "failure": str(e),
                    "projections": projections,
                })
                self._reject_protocol("NON_PROJECTABLE", str(e))
                break
        # 4. conformance: every declared skill refines its projected contract
        #    (S_p <= G|p, Gay-Hole subtyping).  It needs the projections, so
        #    it is skipped when projection already failed.
        if self.protocol_status != "REJECTED":
            rep = conformance_report(self.p.skills, self.p.protocol)
            if not rep.ok:
                trace_artifact("interaction", {
                    "status": "rejected",
                    "check": "conformance",
                    "projections": projections,
                    "failure": rep.failure,
                    "assumed_conformant": list(rep.assumed),
                })
                self._reject_protocol("NON_CONFORMANT", rep.failure)
            else:
                self.assumed_conformant = rep.assumed
                trace_artifact("interaction", {
                    "status": "passed",
                    "projections": projections,
                    "conformance": "passed",
                    "assumed_conformant": list(rep.assumed),
                })
        # T-Comm quantifies over every protocol branch at the same pre-world;
        # T-Act and T-Goal then check guards/markers in lockstep.  Projection
        # alone only checks process shape, so decide these world premises too.
        typing_condition = (self._direct_typing_condition()
                            if self.protocol_status == "WELL_TYPED" else None)
        # 5. tolerant may-reachability of the goal
        ok, end_state = self._reach(self.p.protocol, initial_state(self.p), {})
        if ok:
            witness = end_state.path
            if self.protocol_status == "WELL_TYPED":
                # Search again with the shared-world premise at each goal.
                # Rejecting only the first witness would miss compatible
                # later branches; omitting the goal would admit incompatible
                # worlds.  This is a typing check: its failure rejects the
                # protocol, while the goal stays reachable along the witness
                # of the first search.
                self.typing_condition = typing_condition
                self.loop_seen.clear()
                self.blocked.clear()
                self.defeated.clear()
                typed, typed_state = self._reach(
                    self.p.protocol, initial_state(self.p), {})
                self.typing_condition = None
                if typed:
                    # prefer the witness that is also typing-consistent
                    witness, end_state = typed_state.path, typed_state
                else:
                    trace_artifact("interaction", {
                        "status": "rejected",
                        "check": "whole-session typing",
                        "failure": "whole-session typing rejected every witness",
                        "blocked": list(self.blocked),
                        "defeated": list(self.defeated),
                    })
                    self._reject_protocol(
                        "NON_CONFORMANT",
                        "a may-reachability witness exists, but the whole-session "
                        "T-Comm/T-Act/T-Goal judgment has no derivation from the "
                        "same initial world: the protocol-wide guards and goal "
                        "markers are inconsistent with the witness")
            trace_artifact("reachability", {
                "status": "passed",
                "witness": _jsonable(witness),
                "terminal_predicates": sorted(end_state.true_preds),
            })
            return Verdict(True, "OK", "goal reachable along witness path",
                           witness=witness)
        if self.defeated:
            uniq = tuple(dict.fromkeys(self.defeated))
            trace_artifact("reachability", {
                "status": "refuted",
                "reason": "external branch defeats the goal",
                "frontier": list(uniq),
            })
            return Verdict(False, "GOAL_UNSAT",
                           "adversarially unachievable: " + "; ".join(uniq),
                           frontier=uniq)
        if self.missing_hit:
            # the search treated steps with a missing tool as dead ends, and
            # the paths that avoid them do not reach the goal either
            uniq = tuple(sorted(self.missing_hit))
            trace_artifact("reachability", {
                "status": "refuted",
                "reason": "every goal-reaching path needs a missing tool or is blocked",
                "frontier": list(uniq),
            })
            other = "; ".join(dict.fromkeys(self.blocked)) or "no other path reaches the goal"
            return Verdict(False, "MISSING_CAPABILITY",
                           f"protocol invokes undeclared capabilities: {list(uniq)}; "
                           f"the paths that avoid them fail: {other}",
                           frontier=uniq)
        if self.blocked:
            uniq = tuple(dict.fromkeys(self.blocked))
            trace_artifact("reachability", {
                "status": "refuted",
                "reason": "mandatory action guard is blocked",
                "frontier": list(uniq),
            })
            return Verdict(False, "BLOCKED_GUARD", "; ".join(uniq), frontier=uniq)
        trace_artifact("reachability", {
            "status": "refuted",
            "reason": "protocol terminates without satisfying the goal",
        })
        return Verdict(False, "GOAL_UNSAT",
                       "protocol terminates but no run satisfies the goal "
                       "(goal predicate never established / refinement unsatisfiable)")

    def _skip_traces(
        self,
        reason: str,
        *,
        interaction: bool = False,
        reachability: bool = False,
    ) -> None:
        if interaction:
            trace_artifact("interaction", {"status": "skipped", "reason": reason})
        if reachability:
            trace_artifact("reachability", {"status": "skipped", "reason": reason})

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
            values[var] = eval_expr(expr, st)
        for var, formula in cap.nondet.items():
            if var in cap.assigns:
                continue
            fresh = self._fresh_typing_value(var)
            formula_values = dict(old)
            formula_values[var] = fresh
            formula_state = _mk_typing_state(st.true_preds, formula_values)
            constraints.append(eval_formula(formula, formula_state))
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
                eval_formula(step["goal"], st),
                self._typing_condition(rest, st, recenv, seen))
        if "msg" in step:
            return self._typing_condition(rest, st, recenv, seen)
        if "act" in step:
            cap = self.p.capabilities[step["act"]["cap"]]
            post, effect_constraints = self._typing_effect(st, cap)
            return z3.And(
                eval_formula(cap.pre, st),
                *effect_constraints,
                self._typing_condition(rest, post, recenv, seen))
        if "choice" in step:
            assumes = step["choice"].get("assumes") or {}
            return z3.And([
                self._typing_condition(
                    list(branch) + rest,
                    _mk_typing_state(st.true_preds | set(assumes.get(label, ())),
                                     st.env()) if assumes.get(label) else st,
                    recenv, frozenset(seen))
                for label, branch in step["choice"]["branches"].items()
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
        initial = [eval_formula(f, st)
                   for f in self.p.init_constraints]
        condition = self._typing_condition(
            self.p.protocol, st, {}, frozenset())
        return z3.And(*initial, condition)

    def _avoids_missing(self, steps: list[dict], missing: set[str],
                        recenv: dict) -> bool:
        """Is there a path through `steps` to a goal point (an explicit goal
        marker or the end of the protocol) that fires no tool in `missing`?

        Guards and effects are ignored, so this over-approximates the paths
        a run can take: when it answers False, every run that reaches a goal
        point fires a missing tool, which World-Act cannot do, so the goal is
        unreachable.  A `continue` ends the path: a run that leaves a
        tail-recursive loop does so from the loop head, so if any iteration
        can leave without a missing tool, a single iteration can.  Under
        adversarial semantics an external choice needs every branch."""
        for i, s in enumerate(steps):
            if "goal" in s:
                return True
            if "act" in s and s["act"]["cap"] in missing:
                return False
            if "continue" in s:
                return False
            if "rec" in s:
                return self._avoids_missing(
                    list(s["rec"]["body"]) + steps[i + 1:], missing, recenv)
            if "choice" in s:
                rest = steps[i + 1:]
                body = s["choice"]
                results = [self._avoids_missing(list(br) + rest, missing, recenv)
                           for br in body["branches"].values()]
                if self.semantics == "adversarial" and body.get("external", False):
                    return all(results)
                return any(results)
        return True

    def _missing_caps(self, steps: list[dict]) -> set[str]:
        return {s["act"]["cap"] for s in iter_steps(steps)
                if "act" in s and s["act"]["cap"] not in self.p.capabilities}

    def _goal_sat(self, st: State) -> bool:
        constraints = list(st.arith) + [eval_formula(self.p.goal, st)]
        if self.typing_condition is not None:
            constraints.append(self.typing_condition)
        return self._sat(constraints)

    def _widen(self, st: State, label: str) -> State:
        """Back-edge widening: havoc the numeric summary.  Dropping the
        accumulated arithmetic constraints only ENLARGES the reachable set,
        so refutation remains sound (Coq T2); together with the finite
        predicate valuations it makes the loop search terminate (thm:dec)."""
        bumped = {v: n + 1 for v, n in st.versions().items()}
        return _mk_state(st.true_preds, (), bumped,
                         st.path + (("continue", label),))

    def _act(self, cur: State, cap: Capability) -> State | None:
        """The successor of a mandatory action, or None (frontier recorded)
        when its guard or its nondeterministic effect is unsatisfiable."""
        guard = eval_formula(cap.pre, cur)
        if not self._sat(list(cur.arith) + [guard]):
            self.blocked.append(
                f"capability '{cap.name}' guard never satisfiable on "
                f"this path (pre={cap.pre!r})")
            return None
        guarded = _mk_state(cur.true_preds, list(cur.arith) + [guard],
                            cur.versions(), cur.path)
        successor = apply_effect(guarded, cap)
        if not self._sat(list(successor.arith)):
            self.blocked.append(
                f"capability '{cap.name}' has no successor world "
                f"satisfying its nondeterministic effect")
            return None
        return successor

    def _reach(self, steps: list[dict], st: State,
               recenv: dict) -> tuple[bool, State]:
        """(reached_goal, witnessing/end state).  Existential over branches."""
        cur = st
        for i, s in enumerate(steps):
            if "goal" in s:                        # explicit goal marker
                if self._goal_sat(cur):
                    return True, cur
                return False, cur                   # unsatisfied checkpoint
            if "msg" in s:
                cur = _mk_state(cur.true_preds, cur.arith, cur.versions(),
                                cur.path + (("msg", s["msg"]["label"]),))
            elif "act" in s and s["act"]["cap"] not in self.p.capabilities:
                # World-Act cannot fire a tool Gamma lacks: a dead end
                self.missing_hit.add(s["act"]["cap"])
                return False, cur
            elif "act" in s:
                successor = self._act(cur, self.p.capabilities[s["act"]["cap"]])
                if successor is None:
                    return False, cur              # mandatory action blocked
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
                assumes = body.get("assumes") or {}
                for label, br in body["branches"].items():
                    # a branch assumption is a declared fact the branch
                    # establishes on entry, like an `add` effect
                    branch_state = _mk_state(cur.true_preds | set(assumes.get(label, ())),
                                             cur.arith,
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
                             (UNKNOWN / PROTOCOL_ONLY) when the refutation is
                             relative to the declared protocol only. The guard
                             closure ignores deletes and treats numeric
                             comparisons as free Booleans, over-approximating
                             possible producers.

    In both scopes the protocol-typing result (Verdict.protocol) is reported
    separately from the goal label and never turns into IMPOSSIBLE.
    """
    if scope not in {"protocol", "goal"}:
        raise ValueError(f"unknown decision scope: {scope!r}")
    if scope == "goal" and semantics != "may":
        raise ValueError("goal scope supports may semantics only")
    p = normalize(pack)
    trace_artifact("schema", {
        "status": "passed",
        "pack": p.to_dict(),
        "pack_digest": pack_digest(p),
    })
    checker = Checker(p, semantics=semantics)
    certificate = checker._gamma_refutation(guard_closure=True) if scope == "goal" else None
    if certificate is not None:
        v = certificate
        v.protocol = "NOT_CHECKED"
    else:
        v = checker.run()
    v.decision_scope = scope
    if scope == "goal" and v.refuted and not v.context_refuted:
        goal_reason = v.reason
        v.unknown = True
        v.reason = "PROTOCOL_ONLY"
        v.detail = (
            f"refuted relative to the declared protocol only ({goal_reason}); "
            f"no protocol-independent goal refutation was established; "
            f"alternative plans are not ruled out. {v.detail}")
    v.pack_digest = pack_digest(p)
    return v


def _jsonable(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return repr(value)
