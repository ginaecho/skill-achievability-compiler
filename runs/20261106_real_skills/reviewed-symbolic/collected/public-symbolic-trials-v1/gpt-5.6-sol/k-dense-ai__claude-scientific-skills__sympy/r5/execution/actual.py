#!/usr/bin/env python3
import ast
import json
import sys
from pathlib import Path

import sympy as sp

X = sp.Symbol("x")


def parse_expr(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int):
            raise ValueError("only integer literals are allowed")
        return sp.Integer(node.value)
    if isinstance(node, ast.Name):
        if getattr(node, "id") != "x":
            raise ValueError("only x is allowed")
        return X
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = parse_expr(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = parse_expr(node.left)
        right = parse_expr(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if X in right.free_symbols or right == 0:
                raise ValueError("divisor must be a nonzero constant")
            return left / right
        if isinstance(node.op, ast.Pow):
            # The exponent must be a literal integer from zero through eight.
            if not isinstance(node.right, ast.Constant):
                raise ValueError("power must be a literal")
            exponent = node.right.value
            if isinstance(exponent, bool) or not isinstance(exponent, int) or not 0 <= exponent <= 8:
                raise ValueError("invalid power")
            return left ** exponent
    raise ValueError("unsupported expression")


def parse_roots_line(text):
    source = text.split("#", 1)[0].strip()
    tree = ast.parse(source, mode="eval")
    call = tree.body
    if not (isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and getattr(call.func, "id") == "roots"
            and len(call.args) == 2
            and not call.keywords
            and isinstance(call.args[1], ast.Name)
            and call.args[1].id == "x"):
        raise ValueError("invalid roots call")
    return parse_expr(call.args[0])


def rational_string(value):
    value = sp.Rational(value)
    if value.q == 1:
        return str(value.p)
    return f"{value.p}/{value.q}"


def make_case(expr):
    poly = sp.Poly(expr, X, domain=sp.QQ)
    if poly.is_zero:
        raise ValueError("zero polynomial is not allowed")

    root_map = sp.polys.polytools.ground_roots(poly)
    ordered = sorted((sp.Rational(root), int(mult))
                     for root, mult in root_map.items())

    residual = poly
    for root, multiplicity in ordered:
        factor = sp.Poly(X - root, X, domain=sp.QQ)
        for _ in range(multiplicity):
            residual = residual.exquo(factor)

    return {
        "coefficients": [rational_string(c) for c in poly.all_coeffs()],
        "rational_roots": [
            {"root": rational_string(root), "multiplicity": multiplicity}
            for root, multiplicity in ordered
        ],
        "residual_coefficients": [rational_string(c) for c in residual.all_coeffs()],
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit(2)
    cases = []
    with Path(sys.argv[1]).open("r", encoding="utf-8", newline=None) as source:
        for line in source:
            if line.strip().startswith("roots("):
                cases.append(make_case(parse_roots_line(line)))
    sys.stdout.write(json.dumps({"cases": cases}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
