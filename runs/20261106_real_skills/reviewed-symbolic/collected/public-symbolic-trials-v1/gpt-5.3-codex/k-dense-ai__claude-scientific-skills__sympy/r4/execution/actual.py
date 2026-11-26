#!/usr/bin/env python3
import json
import re
import sys
from sympy import Integer, Poly, Rational, Symbol
from sympy.parsing.sympy_parser import (
    parse_expr,
    standard_transformations,
    convert_xor,
)


LINE_RE = re.compile(r"^roots\((.*),\s*x\)\s*(?:#.*)?$")
ALLOWED_EXPR_RE = re.compile(r"^[0-9xX\s+\-*/^()]*$")
TRANSFORMS = standard_transformations + (convert_xor,)


def rat_to_str(v):
    r = Rational(v)
    p, q = int(r.p), int(r.q)
    if q == 1:
        return str(p)
    return f"{p}/{q}"


def parse_polynomial(expr_text, x):
    if not ALLOWED_EXPR_RE.fullmatch(expr_text):
        raise ValueError("Expression contains unsupported characters")
    expr = parse_expr(
        expr_text,
        local_dict={"x": x, "X": x},
        global_dict={"__builtins__": {}, "Integer": Integer, "Rational": Rational},
        transformations=TRANSFORMS,
        evaluate=True,
    )
    poly = Poly(expr, x, domain="QQ")
    if poly.is_zero:
        raise ValueError("Zero polynomial is unsupported")
    return poly


def process_file(path):
    x = Symbol("x")
    cases = []
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            stripped = raw_line.strip()
            if not stripped.startswith("roots("):
                continue
            m = LINE_RE.fullmatch(stripped)
            if not m:
                continue
            expr_text = m.group(1).strip()
            poly = parse_polynomial(expr_text, x)

            coeffs = [rat_to_str(c) for c in poly.all_coeffs()]

            roots_map = poly.ground_roots()
            rational_items = sorted(roots_map.items(), key=lambda kv: kv[0])

            divisor = Poly(1, x, domain="QQ")
            rational_roots = []
            for root, mult in rational_items:
                root_r = Rational(root)
                mult_i = int(mult)
                divisor *= Poly(x - root_r, x, domain="QQ") ** mult_i
                rational_roots.append({"root": rat_to_str(root_r), "multiplicity": mult_i})

            residual = poly.quo(divisor)
            residual_coeffs = [rat_to_str(c) for c in residual.all_coeffs()]

            cases.append(
                {
                    "coefficients": coeffs,
                    "rational_roots": rational_roots,
                    "residual_coefficients": residual_coeffs,
                }
            )
    return {"cases": cases}


def main():
    if len(sys.argv) != 2:
        return 1
    out = process_file(sys.argv[1])
    sys.stdout.write(json.dumps(out, ensure_ascii=False))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
