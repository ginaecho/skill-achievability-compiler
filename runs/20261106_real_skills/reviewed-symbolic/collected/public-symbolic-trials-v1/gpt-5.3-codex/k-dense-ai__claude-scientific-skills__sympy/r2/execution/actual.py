#!/usr/bin/env python3
import ast
import json
import re
import sys
from fractions import Fraction

from sympy import Integer, Poly, QQ, Rational, Symbol


ROOTS_LINE_RE = re.compile(r"^roots\((.*),\s*x\s*\)\s*(?:#.*)?$")


def rational_str(value):
    q = Rational(value)
    p = int(q.p)
    d = int(q.q)
    if d == 1:
        return str(p)
    return f"{p}/{d}"


def _eval_ast(node, x):
    if isinstance(node, ast.Expression):
        return _eval_ast(node.body, x)

    if isinstance(node, ast.Name):
        if node.id != "x":
            raise ValueError("Only variable x is allowed")
        return x

    if isinstance(node, ast.Constant):
        if type(node.value) is not int:
            raise ValueError("Only integer literals are allowed")
        return Integer(node.value)

    if isinstance(node, ast.UnaryOp):
        val = _eval_ast(node.operand, x)
        if isinstance(node.op, ast.UAdd):
            return val
        if isinstance(node.op, ast.USub):
            return -val
        raise ValueError("Unsupported unary operator")

    if isinstance(node, ast.BinOp):
        left = _eval_ast(node.left, x)
        right = _eval_ast(node.right, x)

        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if getattr(right, "free_symbols", set()):
                raise ValueError("Division denominator must be constant")
            right_q = Rational(right)
            if right_q == 0:
                raise ValueError("Division by zero")
            return left / right_q
        if isinstance(node.op, ast.Pow):
            exp_q = Rational(right)
            if exp_q.q != 1:
                raise ValueError("Exponent must be an integer")
            exp = int(exp_q.p)
            if exp < 0 or exp > 8:
                raise ValueError("Exponent out of allowed range")
            return left ** exp
        raise ValueError("Unsupported binary operator")

    raise ValueError("Unsupported syntax")


def parse_expr_text(expr_text, x):
    tree = ast.parse(expr_text, mode="eval")
    expr = _eval_ast(tree, x)
    if getattr(expr, "free_symbols", set()) - {x}:
        raise ValueError("Only variable x is allowed")
    return expr


def polynomial_case(expr_text, x):
    expr = parse_expr_text(expr_text, x)
    poly = Poly(expr, x, domain=QQ)

    coefficients = [rational_str(c) for c in poly.all_coeffs()]

    _, factors = poly.factor_list()
    roots_mult = {}
    for fac, mult in factors:
        if fac.degree() == 1:
            a, b = fac.all_coeffs()
            root = Rational(-b, a)
            roots_mult[root] = roots_mult.get(root, 0) + int(mult)

    ordered_roots = sorted(roots_mult.items(), key=lambda kv: Fraction(int(kv[0].p), int(kv[0].q)))

    residual = poly
    for root, mult in ordered_roots:
        residual = residual.exquo(Poly(x - root, x, domain=QQ) ** mult)

    residual_coefficients = [rational_str(c) for c in residual.all_coeffs()]

    rational_roots = [
        {"root": rational_str(root), "multiplicity": mult}
        for root, mult in ordered_roots
    ]

    return {
        "coefficients": coefficients,
        "rational_roots": rational_roots,
        "residual_coefficients": residual_coefficients,
    }


def main():
    if len(sys.argv) != 2:
        raise SystemExit(2)

    input_path = sys.argv[1]
    x = Symbol("x")
    cases = []

    with open(input_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped.startswith("roots("):
                continue
            m = ROOTS_LINE_RE.match(stripped)
            if not m:
                continue
            expr_text = m.group(1).strip()
            cases.append(polynomial_case(expr_text, x))

    sys.stdout.write(json.dumps({"cases": cases}, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
