#!/usr/bin/env python3
"""Find exact rational roots (with multiplicity) of roots(EXPR, x) lines in a Markdown file."""
import json
import re
import sys
from fractions import Fraction

from sympy import Poly, QQ, Symbol

X = Symbol("x")
MAXPOW = 8


class ParseError(Exception):
    pass


# ---- polynomial helpers: list of Fraction, lowest-degree-first ----
def trim(p):
    p = list(p)
    while len(p) > 1 and p[-1] == 0:
        p.pop()
    return p or [Fraction(0)]


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
    return trim(r)


def is_const(a):
    return len(trim(a)) == 1


# ---- safe recursive-descent parser ----
TOKEN = re.compile(r"\s*(?:(\d+)|(\*\*)|([x])|([-+*/()]))")


def tokenize(s):
    pos, out = 0, []
    s = s.rstrip()
    while pos < len(s):
        m = TOKEN.match(s, pos)
        if not m or m.end() == pos:
            raise ParseError("bad token at %d" % pos)
        num, pw, var, op = m.groups()
        if num is not None:
            out.append(("num", int(num)))
        elif pw:
            out.append(("op", "**"))
        elif var:
            out.append(("x", None))
        else:
            out.append(("op", op))
        pos = m.end()
    return out


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def take(self):
        tok = self.peek()
        self.i += 1
        return tok

    def parse(self):
        r = self.expr()
        if self.i != len(self.t):
            raise ParseError("trailing tokens")
        return r

    def expr(self):
        r = self.term()
        while self.peek() in (("op", "+"), ("op", "-")):
            op = self.take()[1]
            rhs = self.term()
            r = padd(r, rhs if op == "+" else pneg(rhs))
        return r

    def term(self):
        r = self.unary()
        while self.peek() in (("op", "*"), ("op", "/")):
            op = self.take()[1]
            rhs = self.unary()
            if op == "*":
                r = pmul(r, rhs)
            else:
                if not is_const(rhs) or rhs[0] == 0:
                    raise ParseError("division by non-constant or zero")
                r = [c / rhs[0] for c in r]
        return r

    def unary(self):
        if self.peek() == ("op", "-"):
            self.take()
            return pneg(self.unary())
        if self.peek() == ("op", "+"):
            self.take()
            return self.unary()
        return self.power()

    def power(self):
        base = self.atom()
        if self.peek() == ("op", "**"):
            self.take()
            kind, val = self.take()
            if kind != "num" or val > MAXPOW:
                raise ParseError("exponent must be a literal integer 0..8")
            r = [Fraction(1)]
            for _ in range(val):
                r = pmul(r, base)
            return r
        return base

    def atom(self):
        kind, val = self.take()
        if kind == "num":
            return [Fraction(val)]
        if kind == "x":
            return [Fraction(0), Fraction(1)]
        if (kind, val) == ("op", "("):
            r = self.expr()
            if self.take() != ("op", ")"):
                raise ParseError("missing )")
            return r
        raise ParseError("unexpected token")


def extract_expr(stripped):
    """stripped begins with 'roots('. Return EXPR text of roots(EXPR, x) [# comment]."""
    body = stripped[len("roots("):]
    depth = 0
    for i, ch in enumerate(body):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth < 0:
                raise ParseError("unbalanced")
        elif ch == "," and depth == 0:
            rest = body[i + 1:]
            m = re.fullmatch(r"\s*x\s*\)\s*(#.*)?", rest)
            if not m:
                raise ParseError("bad roots() tail")
            return body[:i]
    raise ParseError("no top-level comma")


def fstr(q):
    q = Fraction(q)
    return str(q.numerator) if q.denominator == 1 else "%d/%d" % (q.numerator, q.denominator)


def analyse(p_low):
    coeffs = list(reversed(trim(p_low)))  # highest first
    roots = {}
    if len(coeffs) > 1:
        poly = Poly([QQ(c.numerator, c.denominator) for c in coeffs], X, domain=QQ)
        _, factors = poly.factor_list()
        for f, mult in factors:
            if f.degree() == 1:
                a, b = f.all_coeffs()
                r = Fraction(-Fraction(int(b.numerator), int(b.denominator))
                             / Fraction(int(a.numerator), int(a.denominator)))
                roots[r] = roots.get(r, 0) + int(mult)
    # residual: synthetic division of ORIGINAL coefficients by (x - r) repeatedly
    resid = list(coeffs)
    for r, m in roots.items():
        for _ in range(m):
            out, acc = [], Fraction(0)
            for c in resid:
                acc = acc * r + c
                out.append(acc)
            if out[-1] != 0:
                raise ArithmeticError("non-exact division")
            resid = out[:-1]
    return {
        "coefficients": [fstr(c) for c in coeffs],
        "rational_roots": [{"root": fstr(r), "multiplicity": roots[r]} for r in sorted(roots)],
        "residual_coefficients": [fstr(c) for c in resid],
    }


def main(argv):
    if len(argv) != 2:
        sys.stdout.write(json.dumps({"error": "usage: roots.py INPUT.md"}) + "\n")
        return 2
    with open(argv[1], "r", encoding="utf-8-sig", newline="") as fh:
        text = fh.read()
    cases = []
    for line in re.split(r"\r\n|\n|\r", text):
        stripped = line.strip()
        if not stripped.startswith("roots("):
            continue
        expr = extract_expr(stripped)
        cases.append(analyse(Parser(tokenize(expr)).parse()))
    sys.stdout.write(json.dumps({"cases": cases}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
