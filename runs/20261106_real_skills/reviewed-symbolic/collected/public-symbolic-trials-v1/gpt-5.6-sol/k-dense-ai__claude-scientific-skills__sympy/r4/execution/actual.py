#!/usr/bin/env python3
import ast
import json
import sys
from pathlib import Path

import sympy as sp

x = sp.Symbol("x")


def _nonnegative_integer_literal(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.UAdd):
        return _nonnegative_integer_literal(node.operand)
    raise ValueError("power must be an integer literal")


def _expression(node):
    if isinstance(node, ast.Constant) and type(node.value) is int:
        return sp.Integer(node.value)
    if isinstance(node, ast.Name) and getattr(node, "id") == "x":
        return x
    if isinstance(node, ast.UnaryOp):
        value = _expression(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        raise ValueError("unsupported unary operator")
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            exponent = _nonnegative_integer_literal(node.right)
            if not 0 <= exponent <= 8:
                raise ValueError("power out of range")
            return _expression(node.left) ** exponent
        left = _expression(node.left)
        right = _expression(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if right.has(x) or right == 0:
                raise ValueError("divisor must be a nonzero constant")
            return left / right
        raise ValueError("unsupported binary operator")
    raise ValueError("unsupported expression")


def _rational_string(value):
    value = sp.Rational(value)
    if value.q == 1:
        return str(value.p)
    return f"{value.p}/{value.q}"


def _case_from_line(line):
    parsed = ast.parse(line.strip(), mode="eval").body
    if not (
        isinstance(parsed, ast.Call)
        and isinstance(parsed.func, ast.Name)
        and getattr(parsed.func, "id") == "roots"
        and len(parsed.args) == 2
        and not parsed.keywords
        and isinstance(parsed.args[1], ast.Name)
        and parsed.args[1].id == "x"
    ):
        raise ValueError("invalid roots line")

    polynomial = sp.Poly(_expression(parsed.args[0]), x, domain=sp.QQ)
    if polynomial.is_zero:
        raise ValueError("zero polynomial")

    roots = polynomial.ground_roots()
    ordered_roots = sorted(roots)
    residual = polynomial
    root_records = []
    for root in ordered_roots:
        multiplicity = int(roots[root])
        root_records.append({
            "root": _rational_string(root),
            "multiplicity": multiplicity,
        })
        factor = sp.Poly(x - root, x, domain=sp.QQ) ** multiplicity
        residual = residual.exquo(factor)

    return {
        "coefficients": [_rational_string(c) for c in polynomial.all_coeffs()],
        "rational_roots": root_records,
        "residual_coefficients": [_rational_string(c) for c in residual.all_coeffs()],
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit(2)
    cases = []
    text = Path(sys.argv[1]).read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.strip().startswith("roots("):
            cases.append(_case_from_line(line))
    sys.stdout.write(json.dumps({"cases": cases}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
