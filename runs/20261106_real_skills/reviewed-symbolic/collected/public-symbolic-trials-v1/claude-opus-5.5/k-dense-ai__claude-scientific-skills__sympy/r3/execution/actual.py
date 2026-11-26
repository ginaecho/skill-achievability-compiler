#!/usr/bin/env python3
"""Find rational roots of roots(EXPR, x) lines in a Markdown file (data only)."""
import ast
import json
import sys
from fractions import Fraction


class ParseError(Exception):
    pass


def trim(p):
    p = list(p)
    while len(p) > 1 and p[0] == 0:
        p.pop(0)
    return p or [Fraction(0)]


def add(a, b):
    n = max(len(a), len(b))
    a = [Fraction(0)] * (n - len(a)) + a
    b = [Fraction(0)] * (n - len(b)) + b
    return trim([u + v for u, v in zip(a, b)])


def neg(a):
    return [-c for c in a]


def mul(a, b):
    r = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, u in enumerate(a):
        if u:
            for j, v in enumerate(b):
                r[i + j] += u * v
    return trim(r)


def divmod_poly(a, b):
    a = trim(a)
    b = trim(b)
    if len(a) < len(b):
        return [Fraction(0)], a
    q = [Fraction(0)] * (len(a) - len(b) + 1)
    r = list(a)
    for i in range(len(q)):
        c = r[i] / b[0]
        q[i] = c
        if c:
            for j, v in enumerate(b):
                r[i + j] -= c * v
    rem = trim(r[len(q):] if len(b) > 1 else [Fraction(0)])
    return trim(q), rem


def evaluate(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int):
            raise ParseError("bad literal")
        return [Fraction(node.value)]
    if isinstance(node, ast.Name):
        if node.id != "x":
            raise ParseError("bad name")
        return [Fraction(1), Fraction(0)]
    if isinstance(node, ast.UnaryOp):
        v = evaluate(node.operand)
        if isinstance(node.op, ast.USub):
            return neg(v)
        if isinstance(node.op, ast.UAdd):
            return v
        raise ParseError("bad unary op")
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            e = node.right
            if not (isinstance(e, ast.Constant) and isinstance(e.value, int)
                    and not isinstance(e.value, bool) and 0 <= e.value <= 8):
                raise ParseError("bad exponent")
            base = evaluate(node.left)
            r = [Fraction(1)]
            for _ in range(e.value):
                r = mul(r, base)
            return r
        a = evaluate(node.left)
        b = evaluate(node.right)
        if isinstance(node.op, ast.Add):
            return add(a, b)
        if isinstance(node.op, ast.Sub):
            return add(a, neg(b))
        if isinstance(node.op, ast.Mult):
            return mul(a, b)
        if isinstance(node.op, ast.Div):
            if len(b) != 1 or b[0] == 0:
                raise ParseError("division by non-constant or zero")
            return [c / b[0] for c in a]
        raise ParseError("bad binary op")
    raise ParseError("unsupported syntax")


def extract_call(stripped):
    """Return text of roots(...) call up to its matching parenthesis."""
    depth = 0
    for i, ch in enumerate(stripped):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                rest = stripped[i + 1:].strip()
                if rest and not rest.startswith("#"):
                    raise ParseError("trailing text")
                return stripped[:i + 1]
        elif ch == "#" and depth > 0:
            raise ParseError("comment inside call")
    raise ParseError("unbalanced")


def parse_line(stripped):
    call = extract_call(stripped)
    tree = ast.parse(call, mode="eval").body
    if not (isinstance(tree, ast.Call) and isinstance(tree.func, ast.Name)
            and tree.func.id == "roots" and len(tree.args) == 2
            and not tree.keywords and isinstance(tree.args[1], ast.Name)
            and tree.args[1].id == "x"):
        raise ParseError("not roots(EXPR, x)")
    return evaluate(tree.args[0])


def divisors(n):
    n = abs(n)
    small, large = [], []
    d = 1
    while d * d <= n:
        if n % d == 0:
            small.append(d)
            if d * d != n:
                large.append(n // d)
        d += 1
    return small + large[::-1]


def gcd_list(vals):
    from math import gcd
    g = 0
    for v in vals:
        g = gcd(g, v)
    return g


def primitive_int(p):
    from math import lcm
    den = 1
    for c in p:
        den = lcm(den, c.denominator)
    ints = [int(c * den) for c in p]
    g = gcd_list(ints) or 1
    return [Fraction(v // g) for v in ints]


def horner(p, r):
    v = Fraction(0)
    for c in p:
        v = v * r + c
    return v


def rational_roots(p):
    """Return dict root -> multiplicity via exact factorisation over QQ."""
    from sympy import Poly, QQ, Rational, Symbol
    if len(p) <= 1:
        return {}
    x = Symbol("x")
    poly = Poly([Rational(c.numerator, c.denominator) for c in p], x, domain=QQ)
    found = {}
    for fac, mult in poly.factor_list()[1]:
        if fac.degree() == 1:
            a, b = fac.all_coeffs()
            r = -b / a
            fr = Fraction(int(r.p), int(r.q))
            found[fr] = found.get(fr, 0) + int(mult)
    return found


def _brute_rational_roots(p):
    """Reference brute-force rational root search (testing only)."""
    found = {}
    work = primitive_int(p)
    if len(work) <= 1:
        return found
    # zero root
    m = 0
    while len(work) > 1 and work[-1] == 0:
        work.pop()
        m += 1
    if m:
        found[Fraction(0)] = m
    while len(work) > 1:
        work = primitive_int(work)
        a0 = int(work[-1])
        an = int(work[0])
        hit = None
        for q in divisors(an):
            for pp in divisors(a0):
                for s in (1, -1):
                    r = Fraction(s * pp, q)
                    if horner(work, r) == 0:
                        hit = r
                        break
                if hit is not None:
                    break
            if hit is not None:
                break
        if hit is None:
            break
        mult = 0
        while len(work) > 1 and horner(work, hit) == 0:
            work, _ = divmod_poly(work, [Fraction(1), -hit])
            mult += 1
        found[hit] = found.get(hit, 0) + mult
    return found


def fmt(c):
    return str(Fraction(c))


def process(path):
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()
    cases = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("roots("):
            continue
        p = trim(parse_line(stripped))
        rr = rational_roots(p) if any(p) else {}
        resid = p
        for r, m in rr.items():
            for _ in range(m):
                resid, rem = divmod_poly(resid, [Fraction(1), -r])
                assert all(c == 0 for c in rem)
        cases.append({
            "coefficients": [fmt(c) for c in p],
            "rational_roots": [{"root": fmt(r), "multiplicity": int(rr[r])}
                               for r in sorted(rr)],
            "residual_coefficients": [fmt(c) for c in resid],
        })
    return {"cases": cases}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: roots.py INPUT.md\n")
        return 2
    sys.stdout.write(json.dumps(process(argv[1])) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
