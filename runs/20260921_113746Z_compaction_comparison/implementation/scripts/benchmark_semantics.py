"""Independent concrete action semantics for the simulated runtime benchmark.

This module deliberately does not import skillc.checker. Solver models choose
one legal numeric outcome; a simulated run is not a real backend execution.
"""
from __future__ import annotations

import operator
from collections import deque
from typing import Any

import z3

COMPARISONS = {
    "<": operator.lt, "<=": operator.le, "==": operator.eq,
    ">": operator.gt, ">=": operator.ge, "!=": operator.ne,
}
ARITHMETIC = {"+": operator.add, "-": operator.sub, "*": operator.mul}


def expression(expr: Any, values: dict) -> Any:
    if isinstance(expr, int) and not isinstance(expr, bool):
        return expr
    if isinstance(expr, str):
        return values[expr]
    if isinstance(expr, dict) and len(expr) == 1:
        op, args = next(iter(expr.items()))
        if op in ARITHMETIC and isinstance(args, list) and len(args) == 2:
            return ARITHMETIC[op](
                expression(args[0], values), expression(args[1], values))
    raise ValueError(f"unsupported arithmetic expression: {expr!r}")


def formula(form: Any, predicates: set | frozenset, values: dict) -> Any:
    if isinstance(form, bool):
        return z3.BoolVal(form)
    if isinstance(form, str):
        return z3.BoolVal(form in predicates)
    if isinstance(form, dict) and len(form) == 1:
        if "and" in form:
            return z3.And([formula(x, predicates, values) for x in form["and"]])
        if "or" in form:
            return z3.Or([formula(x, predicates, values) for x in form["or"]])
        if "not" in form:
            return z3.Not(formula(form["not"], predicates, values))
        if "cmp" in form:
            left, op, right = form["cmp"]
            result = COMPARISONS[op](
                expression(left, values), expression(right, values))
            return z3.BoolVal(result) if isinstance(result, bool) else result
    raise ValueError(f"unsupported formula: {form!r}")


def holds(form: Any, predicates: set | frozenset, values: dict) -> bool:
    result = z3.simplify(formula(form, predicates, values))
    if z3.is_true(result):
        return True
    if z3.is_false(result):
        return False
    raise ValueError("concrete evaluation retained unbound numeric variables")


def numeric_names(pack: dict) -> set[str]:
    names: set[str] = set()

    def expr(e):
        if isinstance(e, str):
            names.add(e)
        elif isinstance(e, dict):
            for args in e.values():
                for value in args:
                    expr(value)

    def form(f):
        if not isinstance(f, dict):
            return
        if "cmp" in f:
            expr(f["cmp"][0])
            expr(f["cmp"][2])
        elif "not" in f:
            form(f["not"])
        else:
            for args in f.values():
                for value in args:
                    form(value)

    form(pack["goal"])
    for constraint in pack.get("init_constraints", []):
        form(constraint)
    for cap in pack["capabilities"].values():
        form(cap.get("pre", True))
        for name, value in cap.get("assigns", {}).items():
            names.add(name)
            expr(value)
        for name, value in cap.get("nondet", {}).items():
            names.add(name)
            form(value)
    return names


def solve(constraints: list) -> z3.ModelRef | None:
    solver = z3.Solver()
    solver.set(timeout=10_000, random_seed=0)
    solver.add(*constraints)
    status = solver.check()
    if status == z3.unknown:
        raise RuntimeError(f"benchmark solver abstained: {solver.reason_unknown()}")
    return solver.model() if status == z3.sat else None


class World:
    def __init__(self, predicates: set | frozenset, values: dict):
        self.predicates = frozenset(predicates)
        self.values = dict(values)

    @classmethod
    def initial(cls, pack: dict) -> World:
        names = sorted(numeric_names(pack))
        symbols = {name: z3.Int(name) for name in names}
        predicates = set(pack.get("init_true", []))
        model = solve([
            formula(f, predicates, symbols)
            for f in pack.get("init_constraints", [])
        ])
        if model is None:
            raise ValueError("benchmark pack has no legal initial world")
        return cls(predicates, {
            name: model.eval(symbols[name], model_completion=True).as_long()
            for name in names
        })

    def snapshot(self) -> dict:
        return {"true_predicates": sorted(self.predicates),
                "numeric_values": dict(sorted(self.values.items()))}

    def key(self) -> tuple:
        return self.predicates, tuple(sorted(self.values.items()))

    def transition(self, cap: dict, prefer_goal: Any = None) -> tuple[World | None, str | None]:
        if not holds(cap.get("pre", True), self.predicates, self.values):
            return None, "precondition_unsatisfied"
        values = dict(self.values)
        assigns = cap.get("assigns", {})
        for name, expr in assigns.items():
            values[name] = expression(expr, self.values)
        symbols = {}
        constraints = []
        for name, constraint in cap.get("nondet", {}).items():
            if name in assigns:
                continue
            symbols[name] = z3.Int(f"post_{name}")
            constraints.append(formula(
                constraint, self.predicates,
                {**self.values, name: symbols[name]}))
        predicates = (self.predicates | set(cap.get("add", []))) - set(cap.get("del", []))
        model = None
        if prefer_goal is not None:
            model = solve(constraints + [
                formula(prefer_goal, predicates, {**values, **symbols})])
        if model is None:
            model = solve(constraints)
        if model is None:
            return None, "effect_unsatisfiable"
        for name, symbol in symbols.items():
            values[name] = model.eval(symbol, model_completion=True).as_long()
        return World(predicates, values), None


def audit_goal_reachability(pack: dict, max_states: int = 5000) -> dict:
    """Judge any-plan goal reachability, NOT protocol/session conformance.

    A missing-establisher proof is global. Otherwise constructive concrete
    witnesses prove existence. Only exhausted Boolean state spaces prove
    nonexistence; bounded/numeric searches without witnesses abstain.
    """
    establishable = set(pack.get("init_true", []))
    for cap in pack["capabilities"].values():
        establishable.update(cap.get("add", []))

    def closure(f):
        if isinstance(f, bool):
            return z3.BoolVal(f)
        if isinstance(f, str):
            return z3.Bool(f"pred_{f}") if f in establishable else z3.BoolVal(False)
        if "and" in f:
            return z3.And([closure(x) for x in f["and"]])
        if "or" in f:
            return z3.Or([closure(x) for x in f["or"]])
        if "not" in f:
            return z3.Not(closure(f["not"]))
        if "cmp" in f:
            return z3.Bool(f"cmp_{repr(f['cmp'])}")
        raise ValueError(f"unsupported closure formula: {f!r}")

    if solve([closure(pack["goal"])]) is None:
        return {"truth": "IMPOSSIBLE", "basis": "missing_establisher_proof",
                "witness": [], "states": 0}
    initial = World.initial(pack)

    def witnessed(world, path, count):
        return {"truth": "ACHIEVABLE", "basis": "concrete_model_witness",
                "witness": path, "final_state": world.snapshot(),
                "initial_state": initial.snapshot(), "states": count}

    world, path = initial, []
    greedy_seen = set()
    for _ in range(128):
        if holds(pack["goal"], world.predicates, world.values):
            return witnessed(world, path, len(greedy_seen))
        if world.key() in greedy_seen:
            break
        greedy_seen.add(world.key())
        for name, cap in pack["capabilities"].items():
            successor, error = world.transition(cap, pack["goal"])
            if error is None and successor.key() != world.key():
                world = successor
                path = path + [{"capability": name, **world.snapshot()}]
                if holds(pack["goal"], world.predicates, world.values):
                    return witnessed(world, path, len(greedy_seen))
    queue = deque([(initial, [])])
    seen = {initial.key()}
    while queue and len(seen) <= max_states:
        world, path = queue.popleft()
        if holds(pack["goal"], world.predicates, world.values):
            return witnessed(world, path, len(seen))
        for name, cap in pack["capabilities"].items():
            for preference in (pack["goal"], None):
                successor, error = world.transition(cap, preference)
                if error is None and successor.key() not in seen:
                    seen.add(successor.key())
                    queue.append((successor, path + [{
                        "capability": name, **successor.snapshot()}]))
    if not queue and not numeric_names(pack):
        return {"truth": "IMPOSSIBLE", "basis": "exhaustive_boolean_search",
                "witness": [], "states": len(seen)}
    return {"truth": "UNKNOWN", "basis": "incomplete_numeric_or_bounded_search",
            "witness": [], "states": len(seen)}
