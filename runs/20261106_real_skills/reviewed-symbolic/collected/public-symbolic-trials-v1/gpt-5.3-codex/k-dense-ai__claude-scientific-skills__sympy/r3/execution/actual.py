#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

from sympy import Poly, Symbol, sympify


LINE_RE = re.compile(r'^roots\((.*),\s*x\)\s*(?:#.*)?$')


def rat_str(v):
    p, q = v.as_numer_denom()
    p = int(p)
    q = int(q)
    if q < 0:
        p, q = -p, -q
    return str(p) if q == 1 else f"{p}/{q}"


def case_from_expr(expr_text, x):
    expr = sympify(expr_text.replace("^", "**"), locals={"x": x}, evaluate=True)
    poly = Poly(expr, x, domain="QQ")

    coeffs = [rat_str(c) for c in poly.all_coeffs()]

    roots_dict = poly.ground_roots()
    roots_sorted = sorted(roots_dict.items(), key=lambda kv: kv[0])

    rational_roots = [
        {"root": rat_str(r), "multiplicity": int(m)}
        for r, m in roots_sorted
    ]

    residual = poly
    for r, m in roots_sorted:
        factor = Poly(x - r, x, domain="QQ")
        residual = residual.quo(factor ** int(m))

    residual_coeffs = [rat_str(c) for c in residual.all_coeffs()]

    return {
        "coefficients": coeffs,
        "rational_roots": rational_roots,
        "residual_coefficients": residual_coeffs,
    }


def main():
    if len(sys.argv) != 2:
        # Outside valid-input contract; keep output format stable.
        print(json.dumps({"cases": []}, ensure_ascii=False))
        return

    path = sys.argv[1]
    text = Path(path).read_text(encoding="utf-8")

    x = Symbol("x")
    cases = []

    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("roots("):
            continue
        m = LINE_RE.fullmatch(stripped)
        if not m:
            continue
        expr_text = m.group(1).strip()
        cases.append(case_from_expr(expr_text, x))

    print(json.dumps({"cases": cases}, ensure_ascii=False))


if __name__ == "__main__":
    main()
