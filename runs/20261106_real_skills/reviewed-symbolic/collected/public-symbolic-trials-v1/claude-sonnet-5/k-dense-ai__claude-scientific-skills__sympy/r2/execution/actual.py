#!/usr/bin/env python3
"""roots.py - extract roots(EXPR, x) lines from a markdown file and report
exact rational roots (with multiplicities) and residual polynomial.

Only parses the mathematical expression text found on lines whose stripped
text begins with "roots(".  Never executes/imports/evaluates anything from
the document itself; the document is read strictly as inert text data.
"""
import sys
import json
import re

import sympy as sp
from sympy import Symbol, Rational, Poly, sympify, div


X = Symbol('x')

# Only these characters/tokens are permitted inside an expression.  This
# whitelist blocks identifiers, function calls, attribute access, etc., so
# the document can never inject arbitrary code via sympify.
_TOKEN_RE = re.compile(r'\s*(\d+|\*\*|[x+\-*/()])')


def _validate_expr_tokens(expr_str):
    """Ensure expr_str consists solely of whitelisted tokens; raise otherwise."""
    pos = 0
    n = len(expr_str)
    while pos < n:
        m = _TOKEN_RE.match(expr_str, pos)
        if not m:
            raise ValueError("disallowed character in expression: %r" % expr_str[pos:pos + 10])
        pos = m.end()
    return True


def _extract_roots_call(stripped_line):
    """Given a line already known to start with 'roots(', extract the
    EXPR text (raw string) inside roots(EXPR, x), validating the trailing
    content is only whitespace and an optional # comment.

    Returns expr_str, or None if the line does not actually match the
    required 'roots(EXPR, x)' pattern (with optional trailing comment)."""
    assert stripped_line.startswith('roots(')
    i = len('roots(')
    depth = 1
    n = len(stripped_line)
    while i < n and depth > 0:
        c = stripped_line[i]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        i += 1
    if depth != 0:
        return None  # unmatched parens; not a valid roots(...) call

    inner = stripped_line[len('roots('):i - 1]
    rest = stripped_line[i:]
    rest_stripped = rest.lstrip()
    if rest_stripped and not rest_stripped.startswith('#'):
        return None  # trailing junk that is not a comment

    # split inner on the last top-level comma (variable spec must be 'x')
    depth2 = 0
    comma_idx = -1
    for j, ch in enumerate(inner):
        if ch == '(':
            depth2 += 1
        elif ch == ')':
            depth2 -= 1
        elif ch == ',' and depth2 == 0:
            comma_idx = j
    if comma_idx == -1:
        return None

    expr_str = inner[:comma_idx]
    var_str = inner[comma_idx + 1:].strip()
    if var_str != 'x':
        return None
    if not expr_str.strip():
        return None
    return expr_str


def _rational_str(value):
    r = Rational(value)
    if r.q == 1:
        return str(r.p)
    return "%d/%d" % (r.p, r.q)


def _poly_all_coeffs_str(poly):
    coeffs = poly.all_coeffs()
    return [_rational_str(c) for c in coeffs]


def _process_expr(expr_str):
    _validate_expr_tokens(expr_str)
    expr = sympify(expr_str, locals={'x': X}, evaluate=True, rational=True)
    # Must be a univariate polynomial in x over the rationals (division by a
    # nonzero constant keeps this true).
    free = expr.free_symbols
    if free - {X}:
        raise ValueError("unexpected free symbols: %s" % (free,))
    expr_expanded = sp.expand(expr)
    poly = Poly(expr_expanded, X, domain='QQ')

    coefficients = _poly_all_coeffs_str(poly)

    rational_roots_dict = sp.roots(poly, X, filter='Q')

    rational_roots = []
    for root_val, mult in rational_roots_dict.items():
        rational_roots.append((Rational(root_val), int(mult)))
    rational_roots.sort(key=lambda t: t[0])

    # Build residual polynomial: divide the ORIGINAL polynomial by every
    # monic factor (x - root)**multiplicity, keeping original leading
    # scalar (i.e. do not renormalize/monic-ize the result).
    residual_poly = poly
    for root_val, mult in rational_roots:
        factor_poly = Poly(X - root_val, X, domain='QQ')
        for _ in range(mult):
            q, r = div(residual_poly, factor_poly, X, domain='QQ')
            if not r.is_zero:
                raise ValueError("exact division by root factor failed")
            residual_poly = q

    residual_coefficients = _poly_all_coeffs_str(residual_poly)

    rational_roots_out = [
        {"root": _rational_str(root_val), "multiplicity": mult}
        for root_val, mult in rational_roots
    ]

    return {
        "coefficients": coefficients,
        "rational_roots": rational_roots_out,
        "residual_coefficients": residual_coefficients,
    }


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: roots.py <markdown-path>\n")
        return 2

    path = sys.argv[1]
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    cases = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith('roots('):
            continue
        expr_str = _extract_roots_call(stripped)
        if expr_str is None:
            continue
        case = _process_expr(expr_str)
        cases.append(case)

    sys.stdout.write(json.dumps({"cases": cases}) + "\n")
    return 0


if __name__ == '__main__':
    sys.exit(main())
