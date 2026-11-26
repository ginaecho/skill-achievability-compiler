#!/usr/bin/env python3
"""Extract declared polynomial root examples from a Markdown file."""

import ast
import json
import sys
from pathlib import Path

import sympy as sp


x = sp.Symbol("x")


def _constant(node):
    """Evaluate an x-free arithmetic subtree, or raise ValueError."""
    value = _expression(node, allow_x=False)
    if value.has(x):
        raise ValueError("divisor must be constant")
    return value


def _expression(node, allow_x=True):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int):
            raise ValueError("only integer literals are allowed")
        return sp.Integer(node.value)
    if isinstance(node, ast.Name):
        if allow_x and getattr(node, "id") == "x":
            return x
        raise ValueError("unexpected name")
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _expression(node.operand, allow_x)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            # The exponent is deliberately required to be an unsigned literal.
            if (not isinstance(node.right, ast.Constant)
                    or isinstance(node.right.value, bool)
                    or not isinstance(node.right.value, int)
                    or not 0 <= node.right.value <= 8):
                raise ValueError("invalid power")
            return _expression(node.left, allow_x) ** node.right.value
        if isinstance(node.op, ast.Div):
            numerator = _expression(node.left, allow_x)
            denominator = _constant(node.right)
            if denominator == 0:
                raise ValueError("division by zero")
            return numerator / denominator
        left = _expression(node.left, allow_x)
        right = _expression(node.right, allow_x)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
    raise ValueError("unsupported expression")


def _parse_line(line):
    text = line.strip()
    if not text.startswith("roots("):
        return None
    # The declared input language has no strings, so '#' unambiguously starts
    # the optional Markdown example comment.
    source = text.split("#", 1)[0].rstrip()
    tree = ast.parse(source, mode="eval").body
    if (not isinstance(tree, ast.Call)
            or not isinstance(tree.func, ast.Name)
            or getattr(tree.func, "id") != "roots"
            or len(tree.args) != 2
            or tree.keywords
            or not isinstance(tree.args[1], ast.Name)
            or tree.args[1].id != "x"):
        raise ValueError("invalid roots declaration")
    expr = _expression(tree.args[0])
    poly = sp.Poly(expr, x, domain=sp.QQ)
    if poly.is_zero:
        raise ValueError("zero polynomial")
    return poly


def _rational_string(value):
    value = sp.Rational(value)
    if value.q == 1:
        return str(value.p)
    return f"{value.p}/{value.q}"


def _case(poly):
    roots = poly.ground_roots()
    residual = poly
    ordered = sorted((sp.Rational(root), int(mult))
                     for root, mult in roots.items())
    for root, multiplicity in ordered:
        divisor = sp.Poly(x - root, x, domain=sp.QQ) ** multiplicity
        residual = residual.exquo(divisor)
    return {
        "coefficients": [_rational_string(c) for c in poly.all_coeffs()],
        "rational_roots": [
            {"root": _rational_string(root), "multiplicity": multiplicity}
            for root, multiplicity in ordered
        ],
        "residual_coefficients": [
            _rational_string(c) for c in residual.all_coeffs()
        ],
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit(2)
    cases = []
    with Path(sys.argv[1]).open("r", encoding="utf-8", newline=None) as stream:
        for line in stream:
            poly = _parse_line(line)
            if poly is not None:
                cases.append(_case(poly))
    print(json.dumps({"cases": cases}, separators=(",", ":")))


if __name__ == "__main__":
    main()
