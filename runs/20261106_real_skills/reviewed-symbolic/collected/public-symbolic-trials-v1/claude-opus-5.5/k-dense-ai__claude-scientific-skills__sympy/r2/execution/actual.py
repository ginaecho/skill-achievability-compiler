#!/usr/bin/env python3
"""Find rational roots (with multiplicity) of roots(EXPR, x) lines in a Markdown file.

Document content is treated as inert data: expressions are parsed with a
whitelisting AST walker over exact Fractions; nothing is executed.
"""
import ast
import json
import sys
from fractions import Fraction

MAX_DEG = 64  # safety bound on intermediate degree


class InputError(Exception):
    pass


def trim(p):
    p = list(p)
    while len(p) > 1 and p[-1] == 0:
        p.pop()
    return p or [Fraction(0)]


# polynomials stored lowest-degree-first internally
def padd(a, b):
    n = max(len(a), len(b))
    return trim([(a[i] if i < len(a) else 0) + (b[i] if i < len(b) else 0) for i in range(n)])


def pneg(a):
    return [-c for c in a]


def pmul(a, b):
    r = [Fraction(0)] * (len(a) + len(b) - 1)
    for i, ca in enumerate(a):
        if ca:
            for j, cb in enumerate(b):
                r[i + j] += ca * cb
    r = trim(r)
    if len(r) - 1 > MAX_DEG:
        raise InputError("degree too large")
    return r


def is_const(p):
    return len(p) == 1


def ev(node):
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool) or not isinstance(v, int):
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
        a, b = ev(node.left), ev(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return padd(a, b)
        if isinstance(op, ast.Sub):
            return padd(a, pneg(b))
        if isinstance(op, ast.Mult):
            return pmul(a, b)
        if isinstance(op, ast.Div):
            if not is_const(b) or b[0] == 0:
                raise InputError("division only by nonzero constant")
            return trim([c / b[0] for c in a])
        if isinstance(op, ast.Pow):
            if not is_const(b) or b[0].denominator != 1 or b[0] < 0 or b[0] > MAX_DEG:
                raise InputError("bad exponent")
            r = [Fraction(1)]
            for _ in range(int(b[0])):
                r = pmul(r, a)
            return r
        raise InputError("bad binary op")
    raise InputError("unsupported syntax")


def parse_line(stripped):
    code = stripped.split("#", 1)[0].strip()
    try:
        tree = ast.parse(code, mode="eval")
    except SyntaxError as e:
        raise InputError("syntax error: %s" % e)
    call = tree.body
    if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Name)
            and call.func.id == "roots" and len(call.args) == 2 and not call.keywords
            and isinstance(call.args[1], ast.Name) and call.args[1].id == "x"):
        raise InputError("expected roots(EXPR, x)")
    return ev(call.args[0])


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


def synth_div(hi, r):
    """Divide highest-first poly by (x - r); return (quotient, remainder)."""
    q = []
    acc = Fraction(0)
    for c in hi:
        acc = acc * r + c
        q.append(acc)
    rem = q.pop()
    return q, rem


def fmt(f):
    return str(f.numerator) if f.denominator == 1 else "%d/%d" % (f.numerator, f.denominator)


def analyze(low):
    hi = list(reversed(low))  # highest-degree-first
    coeffs = [fmt(c) for c in hi]
    if len(hi) == 1:
        return {"coefficients": coeffs, "rational_roots": [], "residual_coefficients": coeffs}
    mult = {}
    cur = hi[:]
    # zero roots
    while len(cur) > 1 and cur[-1] == 0:
        cur.pop()
        mult[Fraction(0)] = mult.get(Fraction(0), 0) + 1
    if len(cur) > 1:
        # primitive integer polynomial for candidate generation
        from math import gcd
        L = 1
        for c in cur:
            L = L * c.denominator // gcd(L, c.denominator)
        ints = [int(c * L) for c in cur]
        g = 0
        for v in ints:
            g = gcd(g, v)
        ints = [v // g for v in ints]
        cands = []
        for p in divisors(ints[-1]):
            for q in divisors(ints[0]):
                if gcd(p, q) == 1:
                    cands.append(Fraction(p, q))
                    cands.append(Fraction(-p, q))
        cands.sort()
        for r in cands:
            while len(ints) > 1:
                p, q = r.numerator, r.denominator
                # quick necessary conditions: (p - q) | f(1), (p + q) | f(-1)
                f1 = sum(ints)
                fm1 = sum(c if (len(ints) - 1 - i) % 2 == 0 else -c for i, c in enumerate(ints))
                if (p - q) != 0 and f1 % (p - q) != 0:
                    break
                if (p + q) != 0 and fm1 % (p + q) != 0:
                    break
                # exact integer test: sum a_i p^(n-i) q^i == 0
                acc = 0
                qp = 1
                for c in ints:
                    acc = acc * p + c * qp
                    qp *= q
                if acc != 0:
                    break
                # exact division of integer poly by (q*x - p)
                # divide exactly with Fractions, then rescale to a primitive integer poly
                fq, frem = synth_div([Fraction(c) for c in ints], r)
                Lq = 1
                for c in fq:
                    Lq = Lq * c.denominator // gcd(Lq, c.denominator)
                ints2 = [int(c * Lq) for c in fq]
                g2 = 0
                for v in ints2:
                    g2 = gcd(g2, v)
                ints = [v // g2 for v in ints2]
                cur, crem = synth_div(cur, r)
                mult[r] = mult.get(r, 0) + 1
    roots = [{"root": fmt(r), "multiplicity": m} for r, m in sorted(mult.items())]
    return {"coefficients": coeffs, "rational_roots": roots,
            "residual_coefficients": [fmt(c) for c in cur]}


def main(argv):
    if len(argv) != 2:
        sys.stderr.write("usage: roots.py INPUT.md\n")
        return 2
    try:
        with open(argv[1], "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write("cannot read input: %s\n" % e)
        return 2
    cases = []
    try:
        for lineno, line in enumerate(text.splitlines(), 1):
            s = line.strip()
            if not s.startswith("roots("):
                continue
            try:
                cases.append(analyze(parse_line(s)))
            except InputError as e:
                raise InputError("line %d: %s" % (lineno, e))
    except (InputError, RecursionError, MemoryError) as e:
        sys.stderr.write("invalid input: %s\n" % e)
        return 2
    sys.stdout.write(json.dumps({"cases": cases}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
