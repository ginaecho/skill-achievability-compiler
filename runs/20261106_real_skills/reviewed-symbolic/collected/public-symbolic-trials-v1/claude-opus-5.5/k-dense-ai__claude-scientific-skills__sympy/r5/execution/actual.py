#!/usr/bin/env python3
"""Find rational roots of roots(EXPR, x) lines in a Markdown file (data only, never executed)."""
import ast
import json
import sys
from fractions import Fraction

from sympy import Poly, QQ, Symbol

MAXDEG = 8
X = Symbol("x")


class InputError(Exception):
    pass


def trim(p):
    while len(p) > 1 and p[-1] == 0:
        p.pop()
    return p


def padd(a, b):
    n = max(len(a), len(b))
    return trim([(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(n)])


def pneg(a):
    return [-c for c in a]


def pmul(a, b):
    r = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, c in enumerate(a):
        if c:
            for j, d in enumerate(b):
                r[i + j] += c * d
    r = trim(r)
    if len(r) - 1 > 64:
        raise InputError("degree too large")
    return r


def ev(node):
    # polynomials are low-degree-first lists of Fractions
    if isinstance(node, ast.Constant):
        v = node.value
        if type(v) is not int:
            raise InputError("only integer literals allowed")
        return [Fraction(v)]
    if isinstance(node, ast.Name):
        if node.id != "x":
            raise InputError("unknown name %r" % node.id)
        return [Fraction(0), Fraction(1)]
    if isinstance(node, ast.UnaryOp):
        v = ev(node.operand)
        if isinstance(node.op, ast.USub):
            return pneg(v)
        if isinstance(node.op, ast.UAdd):
            return v
        raise InputError("bad unary op")
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            e = node.right
            if not (isinstance(e, ast.Constant) and type(e.value) is int and 0 <= e.value <= MAXDEG):
                raise InputError("exponent must be a literal integer 0..8")
            b = ev(node.left)
            r = [Fraction(1)]
            for _ in range(e.value):
                r = pmul(r, b)
            return r
        a = ev(node.left)
        b = ev(node.right)
        if isinstance(node.op, ast.Add):
            return padd(a, b)
        if isinstance(node.op, ast.Sub):
            return padd(a, pneg(b))
        if isinstance(node.op, ast.Mult):
            return pmul(a, b)
        if isinstance(node.op, ast.Div):
            if len(b) != 1 or b[0] == 0:
                raise InputError("division only by a nonzero constant")
            return [c / b[0] for c in a]
        raise InputError("bad binary op")
    raise InputError("unsupported syntax")


def rstr(q):
    q = Fraction(q)
    return str(q.numerator) if q.denominator == 1 else "%d/%d" % (q.numerator, q.denominator)


def parse_line(s):
    # s is stripped and starts with "roots("; drop optional trailing comment
    if "#" in s:
        s = s[: s.index("#")].rstrip()
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as exc:
        raise InputError("syntax error") from exc
    call = tree.body
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id == "roots"
            and len(call.args) == 2 and not call.keywords
            and isinstance(call.args[1], ast.Name) and call.args[1].id == "x"):
        raise InputError("expected roots(EXPR, x)")
    return ev(call.args[0])


def solve_case(low):
    high = list(reversed(trim(list(low))))
    case = {"coefficients": [rstr(c) for c in high]}
    if len(high) == 1:  # constant (nonzero by contract)
        case["rational_roots"] = []
        case["residual_coefficients"] = [rstr(c) for c in high]
        return case
    p = Poly([QQ(c.numerator, c.denominator) for c in high], X, domain=QQ)
    _, factors = p.factor_list()
    mult = {}
    for f, m in factors:
        if f.degree() == 1:
            a, b = f.all_coeffs()
            r = -Fraction(int(b.numerator), int(b.denominator)) / Fraction(int(a.numerator), int(a.denominator))
            mult[r] = mult.get(r, 0) + int(m)
    # exact synthetic division of the ORIGINAL polynomial by (x - r)^m
    res = list(high)
    for r, m in mult.items():
        for _ in range(m):
            out = [res[0]]
            for c in res[1:]:
                out.append(c + out[-1] * r)
            if out[-1] != 0:
                raise InputError("internal: nonzero remainder")
            res = out[:-1]
    case["rational_roots"] = [{"root": rstr(r), "multiplicity": mult[r]} for r in sorted(mult)]
    case["residual_coefficients"] = [rstr(c) for c in res]
    return case


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: roots.py INPUT.md\n")
        return 2
    try:
        with open(argv[1], "r", encoding="utf-8") as fh:
            text = fh.read()
        cases = []
        for line in text.split("\n"):
            s = line.strip()
            if s.startswith("roots("):
                cases.append(solve_case(parse_line(s)))
    except (OSError, UnicodeDecodeError, InputError, RecursionError) as exc:
        sys.stderr.write("error: %s\n" % exc)
        return 1
    sys.stdout.write(json.dumps({"cases": cases}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
