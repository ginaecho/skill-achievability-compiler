"""The guard/goal mini-language of the achievability pack, compiled to z3.

Grammar (JSON-encoded):

    formula : "predname"                        -- atomic boolean predicate
            | true | false
            | {"and": [formula, ...]}
            | {"or":  [formula, ...]}
            | {"not": formula}
            | {"cmp": [expr, op, expr]}         -- op in  < <= == > >= !=

    expr    : "varname" | int
            | {"+": [expr, expr]}
            | {"-": [expr, expr]}
            | {"*": [expr, expr]}    -- QF-LIA: at least one operand must be
                                        a constant (variable*variable is
                                        nonlinear and is rejected by the gate)

Predicates are Boolean and subject to STRIPS frame semantics (false unless
established by an effect); numeric variables are unbounded integers handled
symbolically by z3.  Keeping expressions linear keeps every solver query
inside QF-LIA, the decidable fragment the paper's decision procedure assumes.
"""
from __future__ import annotations

import operator
from typing import Any
from collections.abc import Callable

import z3

CMP: dict[str, Callable[[Any, Any], z3.BoolRef]] = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "==": lambda a, b: a == b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "!=": lambda a, b: a != b,
}

VALID_OPS = frozenset(CMP)
ARITH: dict[str, Callable[[Any, Any], Any]] = {
    "+": operator.add, "-": operator.sub, "*": operator.mul}


class FormulaError(ValueError):
    """Raised when a formula/expression is structurally malformed."""


def is_constant_expr(e: Any) -> bool:
    """True if `e` denotes an integer constant, i.e. mentions no variable.

    Used to keep multiplication linear: `k * v` and `v * k` are QF-LIA terms,
    `v * w` is not.
    """
    if isinstance(e, bool):
        return False
    if isinstance(e, int):
        return True
    if isinstance(e, dict) and len(e) == 1:
        for k in ARITH:
            if k in e and isinstance(e[k], list) and len(e[k]) == 2:
                return all(is_constant_expr(x) for x in e[k])
    return False


def validate_expr(e: Any, path: str = "expr") -> None:
    """Raise FormulaError if `e` is not a well-formed *linear* expression."""
    if isinstance(e, bool):  # bool is an int subclass; reject explicitly
        raise FormulaError(f"{path}: bad expr {e!r}")
    if isinstance(e, (int, str)):
        return
    if isinstance(e, dict) and len(e) == 1:
        for k in ARITH:
            if k in e:
                if not (isinstance(e[k], list) and len(e[k]) == 2):
                    raise FormulaError(f"{path}: '{k}' needs exactly 2 operands")
                validate_expr(e[k][0], f"{path}.{k}[0]")
                validate_expr(e[k][1], f"{path}.{k}[1]")
                if k == "*" and not (is_constant_expr(e[k][0])
                                     or is_constant_expr(e[k][1])):
                    raise FormulaError(
                        f"{path}: '*' needs at least one integer-constant "
                        f"operand -- the pack language is QF-LIA and "
                        f"variable*variable is nonlinear")
                return
    raise FormulaError(f"{path}: bad expr {e!r}")


def validate_formula(f: Any, path: str = "formula") -> None:
    """Raise FormulaError if `f` is not a well-formed formula."""
    if f is True or f is False:
        return
    if isinstance(f, str):
        return
    if isinstance(f, dict) and len(f) == 1:
        if "and" in f or "or" in f:
            op, seq = next(iter(f.items()))
            if not isinstance(seq, list):
                raise FormulaError(f"{path}: {op} needs a list")
            for i, x in enumerate(seq):
                validate_formula(x, f"{path}.{op}[{i}]")
            return
        if "not" in f:
            validate_formula(f["not"], f"{path}.not")
            return
        if "cmp" in f:
            c = f["cmp"]
            if not (isinstance(c, list) and len(c) == 3 and c[1] in VALID_OPS):
                raise FormulaError(f"{path}: bad cmp {c!r}")
            validate_expr(c[0], f"{path}.cmp[0]")
            validate_expr(c[2], f"{path}.cmp[2]")
            return
    raise FormulaError(f"{path}: bad formula {f!r}")


def atoms(f: Any) -> set[str]:
    """Boolean predicate names appearing in a formula (used for the frame)."""
    if isinstance(f, str):
        return {f}
    if isinstance(f, dict):
        if "and" in f or "or" in f:
            out: set[str] = set()
            for x in f.get("and", []) + f.get("or", []):
                out |= atoms(x)
            return out
        if "not" in f:
            return atoms(f["not"])
    return set()


def numeric_vars(f: Any) -> set[str]:
    """Numeric variable names appearing in a formula's cmp expressions."""
    def expr_vars(e: Any) -> set[str]:
        if isinstance(e, str):
            return {e}
        if isinstance(e, dict):
            out: set[str] = set()
            for k in ARITH:
                for sub in e.get(k, []):
                    out |= expr_vars(sub)
            return out
        return set()

    if isinstance(f, dict):
        if "cmp" in f:
            return expr_vars(f["cmp"][0]) | expr_vars(f["cmp"][2])
        if "and" in f or "or" in f:
            out: set[str] = set()
            for x in f.get("and", []) + f.get("or", []):
                out |= numeric_vars(x)
            return out
        if "not" in f:
            return numeric_vars(f["not"])
    return set()


# --------------------------------------------------------------------------
# Compilation to z3 (one fold, parameterized by how leaves are interpreted)
# --------------------------------------------------------------------------

def compile_expr(e: Any, var: Callable[[str], z3.ArithRef]) -> z3.ArithRef:
    """An expression as a z3 term; `var` interprets variable names."""
    if isinstance(e, int):
        return z3.IntVal(e)
    if isinstance(e, str):
        return var(e)
    if isinstance(e, dict):
        for op, fn in ARITH.items():
            if op in e:
                lhs, rhs = e[op]
                return fn(compile_expr(lhs, var), compile_expr(rhs, var))
    raise ValueError(f"bad expr: {e!r}")


def compile_formula(f: Any, pred: Callable[[str], z3.BoolRef],
                    cmp: Callable[[Any, str, Any], z3.BoolRef]) -> z3.BoolRef:
    """A formula as a z3 Boolean; `pred` interprets predicate atoms and
    `cmp(lhs, op, rhs)` interprets comparisons."""
    if f is True or f is False:
        return z3.BoolVal(f)
    if isinstance(f, str):
        return pred(f)
    if isinstance(f, dict):
        if "and" in f:
            return z3.And([compile_formula(x, pred, cmp) for x in f["and"]])
        if "or" in f:
            return z3.Or([compile_formula(x, pred, cmp) for x in f["or"]])
        if "not" in f:
            return z3.Not(compile_formula(f["not"], pred, cmp))
        if "cmp" in f:
            return cmp(*f["cmp"])
    raise ValueError(f"bad formula: {f!r}")
