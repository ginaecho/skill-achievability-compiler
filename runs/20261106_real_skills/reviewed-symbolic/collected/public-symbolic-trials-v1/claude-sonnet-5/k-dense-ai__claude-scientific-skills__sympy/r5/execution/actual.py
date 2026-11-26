#!/usr/bin/env python3
import sys
import json
import re
import sympy as sp

X = sp.symbols('x')

ALLOWED_CHARS = re.compile(r'^[0-9x\s\+\-\*/\(\)]*$')

def rat_str(r):
    r = sp.nsimplify(r)
    r = sp.Rational(r)
    num = r.p
    den = r.q
    if den == 1:
        return str(num)
    return f"{num}/{den}"

def find_roots_call(line):
    """If stripped line starts with 'roots(', extract (expr_str, rest_ok)."""
    stripped = line.strip()
    if not stripped.startswith("roots("):
        return None
    # find matching close paren for the opening right after 'roots'
    depth = 0
    i = len("roots(") - 1  # index of the '(' char
    start_args = i + 1
    j = i
    n = len(stripped)
    close_idx = None
    while j < n:
        c = stripped[j]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                close_idx = j
                break
        j += 1
    if close_idx is None:
        raise ValueError("Unbalanced parentheses in roots(...) line")
    args_str = stripped[start_args:close_idx]
    remainder = stripped[close_idx+1:]
    # remainder must be optional whitespace then optional '#' comment to end
    rem_stripped = remainder.strip()
    if rem_stripped != "" and not rem_stripped.startswith("#"):
        raise ValueError("Unexpected trailing content after roots(...) call")
    # split args_str on top-level commas (depth relative to args_str, starting at 0)
    parts = []
    depth2 = 0
    last = 0
    for k, c in enumerate(args_str):
        if c == '(':
            depth2 += 1
        elif c == ')':
            depth2 -= 1
        elif c == ',' and depth2 == 0:
            parts.append(args_str[last:k])
            last = k + 1
    parts.append(args_str[last:])
    if len(parts) != 2:
        raise ValueError("roots(...) call must have exactly two top-level arguments")
    expr_str = parts[0].strip()
    var_str = parts[1].strip()
    if var_str != "x":
        raise ValueError("roots(...) second argument must be 'x'")
    if not ALLOWED_CHARS.match(expr_str):
        raise ValueError("Disallowed characters in polynomial expression")
    if '**' in expr_str:
        # validate exponents are nonnegative integer literals (basic safety check)
        for m in re.finditer(r'\*\*\s*(-?\d+)', expr_str):
            if int(m.group(1)) < 0:
                raise ValueError("Negative exponent not allowed")
    return expr_str

def parse_poly_expr(expr_str):
    local_dict = {'x': X}
    transformations = sp.parsing.sympy_parser.standard_transformations
    expr = sp.parsing.sympy_parser.parse_expr(
        expr_str,
        local_dict=local_dict,
        global_dict=None,
        transformations=transformations,
        evaluate=True,
    )
    expr = sp.together(sp.expand(expr))
    return expr

def process_case(expr_str):
    expr = parse_poly_expr(expr_str)
    poly = sp.Poly(expr, X, domain='QQ')
    coeffs = poly.all_coeffs()
    coeffs_str = [rat_str(c) for c in coeffs]

    lc, factors = poly.factor_list()
    rational_roots = []
    for f, m in factors:
        if f.degree() == 1:
            fc = f.all_coeffs()  # [a, b] ; a may not be 1 (non-monic scalar factor)
            a, b = fc[0], fc[1]
            root = sp.Rational(-b, a)
            rational_roots.append((root, m))
    rational_roots.sort(key=lambda t: t[0])

    residual_poly = poly
    for root, m in rational_roots:
        monic_factor = sp.Poly(X - root, X, domain='QQ')
        divisor = monic_factor ** m
        q, r = residual_poly.div(divisor)
        if not r.is_zero:
            raise ValueError("Exact division by rational-root factor failed")
        residual_poly = q
    residual_coeffs = residual_poly.all_coeffs()
    residual_coeffs_str = [rat_str(c) for c in residual_coeffs]

    roots_out = [{"root": rat_str(root), "multiplicity": int(m)} for (root, m) in rational_roots]

    return {
        "coefficients": coeffs_str,
        "rational_roots": roots_out,
        "residual_coefficients": residual_coeffs_str,
    }

def main():
    if len(sys.argv) != 2:
        print("usage: roots.py <input.md>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    cases = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("roots("):
            continue
        expr_str = find_roots_call(line)
        if expr_str is None:
            continue
        case = process_case(expr_str)
        cases.append(case)

    print(json.dumps({"cases": cases}))
    return 0

if __name__ == "__main__":
    sys.exit(main())
