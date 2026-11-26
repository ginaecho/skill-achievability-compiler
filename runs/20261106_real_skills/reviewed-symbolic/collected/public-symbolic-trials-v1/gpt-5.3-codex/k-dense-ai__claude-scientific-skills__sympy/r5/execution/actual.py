#!/usr/bin/env python3
import json
import re
import sys
from sympy import Poly, Rational, Symbol, sympify

x = Symbol('x')
LINE_RE = re.compile(r"roots\((.*),\s*x\)\s*(?:#.*)?$")
SAFE_EXPR_RE = re.compile(r"[0-9x+\-*/^() \t]+$")


def rat_to_str(v):
    r = Rational(v)
    if r.q == 1:
        return str(r.p)
    return f"{r.p}/{r.q}"


def process_expr(expr_text):
    if not SAFE_EXPR_RE.fullmatch(expr_text):
        raise ValueError("unsupported characters in expression")
    expr = sympify(expr_text.replace('^', '**'), locals={'x': x})
    poly = Poly(expr, x, domain='QQ')

    coefficients = [rat_to_str(c) for c in poly.all_coeffs()]

    roots_mult = []
    _, factors = poly.factor_list()
    for fac, mult in factors:
        if fac.degree() == 1:
            a, b = fac.all_coeffs()
            r = -Rational(b) / Rational(a)
            roots_mult.append((Rational(r), int(mult)))

    roots_mult.sort(key=lambda t: t[0])

    residual = poly
    for r, m in roots_mult:
        residual = residual.quo(Poly(x - r, x, domain='QQ') ** m)

    rational_roots = [
        {"root": rat_to_str(r), "multiplicity": m}
        for r, m in roots_mult
    ]
    residual_coefficients = [rat_to_str(c) for c in residual.all_coeffs()]

    return {
        "coefficients": coefficients,
        "rational_roots": rational_roots,
        "residual_coefficients": residual_coefficients,
    }


def main():
    if len(sys.argv) != 2:
        return 1

    in_path = sys.argv[1]
    cases = []

    with open(in_path, 'r', encoding='utf-8') as f:
        for line in f:
            stripped = line.strip()
            if not stripped.startswith('roots('):
                continue
            m = LINE_RE.fullmatch(stripped)
            if not m:
                continue
            expr_text = m.group(1).strip()
            cases.append(process_expr(expr_text))

    out = {"cases": cases}
    sys.stdout.write(json.dumps(out, separators=(',', ':')) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
