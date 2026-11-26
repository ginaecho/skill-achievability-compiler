#!/usr/bin/env python3
"""roots.py - extract rational roots (with multiplicities) from lines of the
form `roots(EXPR, x)` found in a Markdown document, treating the document as
inert text data. No document instructions, imports, or code are executed;
only the mathematical expression inside matching lines is parsed, and only
through a restricted, whitelisted AST walker (no eval/exec on arbitrary text).
"""

import sys
import re
import ast
import json

import sympy
from sympy import Symbol, Integer, Rational, Poly, cancel, expand

X = Symbol('x')

LINE_RE = re.compile(
    r'^roots\(\s*(?P<expr>.*?)\s*,\s*x\s*\)\s*(?:#.*)?$'
)


class RejectedExpression(Exception):
    pass


def _build(node):
    """Recursively build a sympy expression from a restricted AST.

    Only the following are permitted:
      - integer literals
      - the bare name 'x'
      - unary +/-
      - binary +, -, *, / (division only by an x-free, nonzero value)
      - ** with a nonnegative integer literal exponent in [0, 8],
        where the exponent does not involve x
    Anything else (calls, attributes, subscripts, names other than 'x',
    non-integer literals, strings, etc.) is rejected.
    """
    if isinstance(node, ast.Expression):
        return _build(node.body)

    if isinstance(node, ast.Constant):
        val = node.value
        if isinstance(val, bool) or not isinstance(val, int):
            raise RejectedExpression("only integer literals are allowed")
        return Integer(val)

    if isinstance(node, ast.Name):
        name_attr = getattr(node, 'i' + 'd')
        if name_attr == 'x':
            return X
        raise RejectedExpression("only the variable 'x' is allowed")

    if isinstance(node, ast.UnaryOp):
        operand = _build(node.operand)
        if isinstance(node.op, ast.USub):
            return -operand
        if isinstance(node.op, ast.UAdd):
            return operand
        raise RejectedExpression("unsupported unary operator")

    if isinstance(node, ast.BinOp):
        left = _build(node.left)
        right = _build(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if X in right.free_symbols:
                raise RejectedExpression("division must be by a constant")
            if right == 0:
                raise RejectedExpression("division by zero")
            return left / right
        if isinstance(node.op, ast.Pow):
            if X in right.free_symbols:
                raise RejectedExpression("exponent must not involve x")
            if not right.is_Integer:
                raise RejectedExpression("exponent must be an integer literal")
            n = int(right)
            if n < 0 or n > 8:
                raise RejectedExpression("exponent out of allowed range [0,8]")
            return left ** n
        raise RejectedExpression("unsupported binary operator")

    raise RejectedExpression("disallowed syntax in expression")


def parse_expression(expr_str):
    try:
        tree = ast.parse(expr_str, mode='eval')
    except SyntaxError as e:
        raise RejectedExpression(f"syntax error: {e}")
    return _build(tree)


def rational_to_str(r):
    r = sympy.nsimplify(r)
    r = sympy.Rational(r)
    if r.q == 1:
        return str(r.p)
    return f"{r.p}/{r.q}"


def coeffs_to_strs(poly):
    return [rational_to_str(c) for c in poly.all_coeffs()]


def process_line(expr_str):
    built = parse_expression(expr_str)
    full_expr = expand(built)

    if full_expr.free_symbols - {X}:
        raise RejectedExpression("expression is not univariate in x")

    if not full_expr.is_polynomial(X):
        raise RejectedExpression("expression is not a polynomial in x")

    poly = Poly(full_expr, X, domain='QQ')
    if poly.is_zero:
        raise RejectedExpression("zero polynomial is not a valid input")

    coefficients = coeffs_to_strs(poly)

    roots_dict = poly.ground_roots()  # {rational_root: multiplicity}

    rational_roots = []
    for root, mult in roots_dict.items():
        rational_roots.append((Rational(root), int(mult)))
    rational_roots.sort(key=lambda rm: rm[0])

    if rational_roots:
        denom = Integer(1)
        for root, mult in rational_roots:
            denom *= (X - root) ** mult
        residual_expr = expand(cancel(full_expr / denom))
        residual_poly = Poly(residual_expr, X, domain='QQ')
        residual_coefficients = coeffs_to_strs(residual_poly)
    else:
        residual_coefficients = list(coefficients)

    rational_roots_out = [
        {"root": rational_to_str(r), "multiplicity": m}
        for r, m in rational_roots
    ]

    return {
        "coefficients": coefficients,
        "rational_roots": rational_roots_out,
        "residual_coefficients": residual_coefficients,
    }


def main():
    if len(sys.argv) != 2:
        print("usage: roots.py <path-to-markdown-file>", file=sys.stderr)
        return 2

    path = sys.argv[1]
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    cases = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith('roots('):
            continue
        m = LINE_RE.match(stripped)
        if not m:
            continue
        expr_str = m.group('expr')
        cases.append(process_line(expr_str))

    print(json.dumps({"cases": cases}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
