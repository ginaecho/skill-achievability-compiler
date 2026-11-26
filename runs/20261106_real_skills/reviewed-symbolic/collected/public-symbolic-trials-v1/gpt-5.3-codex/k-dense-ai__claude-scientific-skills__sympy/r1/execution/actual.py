#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path
from sympy import Poly, Rational, Symbol, sympify

x = Symbol('x')


def rat_str(v):
    r = Rational(v)
    p, q = int(r.p), int(r.q)
    return str(p) if q == 1 else f"{p}/{q}"


def poly_coeff_strings(poly):
    return [rat_str(c) for c in poly.all_coeffs()]


def extract_case(expr_text):
    expr = sympify(expr_text, locals={'x': x}, evaluate=True)
    poly = Poly(expr, x, domain='QQ')

    roots = []
    for factor_poly, mult in poly.factor_list()[1]:
        if factor_poly.degree() == 1:
            a, b = factor_poly.all_coeffs()
            root = Rational(-b, a)
            roots.append((root, int(mult)))

    roots.sort(key=lambda t: t[0])

    residual = poly
    for root, mult in roots:
        divisor = Poly(x - root, x, domain='QQ')
        for _ in range(mult):
            residual = residual.quo(divisor)

    return {
        'coefficients': poly_coeff_strings(poly),
        'rational_roots': [
            {'root': rat_str(root), 'multiplicity': mult}
            for root, mult in roots
        ],
        'residual_coefficients': poly_coeff_strings(residual),
    }


def main():
    # Keep stdout-only JSON behavior even if called incorrectly.
    if len(sys.argv) != 2:
        print(json.dumps({'cases': []}, separators=(',', ':')))
        return 0

    path = sys.argv[1]
    cases = []

    line_re = re.compile(r'^roots\((.*),\s*x\s*\)\s*(?:#.*)?$')
    text = Path(path).read_text(encoding='utf-8')
    for raw_line in text.splitlines():
        s = raw_line.strip()
        if not s.startswith('roots('):
            continue
        m = line_re.fullmatch(s)
        if not m:
            continue
        expr_text = m.group(1).strip()
        cases.append(extract_case(expr_text))

    print(json.dumps({'cases': cases}, separators=(',', ':')))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception:
        # For robustness, still satisfy stdout-only JSON requirement.
        print(json.dumps({'cases': []}, separators=(',', ':')))
        raise SystemExit(0)
