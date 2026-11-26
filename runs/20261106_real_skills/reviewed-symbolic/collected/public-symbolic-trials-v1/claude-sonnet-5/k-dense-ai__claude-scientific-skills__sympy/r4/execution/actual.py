#!/usr/bin/env python3
import sys
import json
import re
from sympy import Symbol, Integer, Rational, Poly, div as sympy_div

X = Symbol('x')

class ParseError(Exception):
    pass

TOKEN_RE = re.compile(r"\s*(\*\*|[0-9]+|[()+\-*/]|x)")

def tokenize(s):
    tokens = []
    pos = 0
    n = len(s)
    while pos < n:
        m = TOKEN_RE.match(s, pos)
        if not m:
            # check for whitespace only remainder
            if s[pos:].strip() == "":
                break
            raise ParseError("bad token at %r" % s[pos:pos+10])
        tok = m.group(1)
        tokens.append(tok)
        pos = m.end()
    return tokens

class Parser:
    def __init__(self, tokens, varname='x'):
        self.toks = tokens
        self.i = 0
        self.varname = varname

    def peek(self):
        if self.i < len(self.toks):
            return self.toks[self.i]
        return None

    def advance(self):
        t = self.peek()
        self.i += 1
        return t

    def expect(self, tok):
        t = self.advance()
        if t != tok:
            raise ParseError("expected %r got %r" % (tok, t))

    def parse_expr(self):
        node = self.parse_term()
        while self.peek() in ('+', '-'):
            op = self.advance()
            rhs = self.parse_term()
            if op == '+':
                node = node + rhs
            else:
                node = node - rhs
        return node

    def parse_term(self):
        node = self.parse_unary()
        while self.peek() in ('*', '/'):
            op = self.advance()
            rhs = self.parse_unary()
            if op == '*':
                node = node * rhs
            else:
                if rhs.has(X):
                    raise ParseError("division by non-constant")
                if rhs == 0:
                    raise ParseError("division by zero")
                node = node / rhs
        return node

    def parse_unary(self):
        if self.peek() == '+':
            self.advance()
            return self.parse_unary()
        if self.peek() == '-':
            self.advance()
            return -self.parse_unary()
        return self.parse_power()

    def parse_power(self):
        node = self.parse_atom()
        if self.peek() == '**':
            self.advance()
            exp_tok = self.advance()
            if exp_tok is None or not exp_tok.isdigit():
                raise ParseError("expected integer exponent")
            exp = int(exp_tok)
            if exp > 8:
                raise ParseError("exponent too large")
            node = node ** exp
        return node

    def parse_atom(self):
        t = self.peek()
        if t is None:
            raise ParseError("unexpected end")
        if t == '(':
            self.advance()
            node = self.parse_expr()
            self.expect(')')
            return node
        if t.isdigit():
            self.advance()
            return Integer(int(t))
        if t == self.varname:
            self.advance()
            return X
        raise ParseError("unexpected token %r" % t)


def find_roots_call(line):
    """Given a stripped line starting with 'roots(', extract (expr_src, trailing_ok).
    Returns the raw expr substring (between the opening paren after 'roots' and
    the top-level comma), or None if the line does not match the required
    'roots(EXPR, x)' [# comment] pattern."""
    assert line.startswith('roots(')
    rest = line[len('roots('):]
    depth = 0
    i = 0
    n = len(rest)
    comma_idx = None
    while i < n:
        c = rest[i]
        if c == '(':
            depth += 1
        elif c == ')':
            if depth == 0:
                return None
            depth -= 1
        elif c == ',' and depth == 0:
            comma_idx = i
            break
        i += 1
    if comma_idx is None:
        return None
    expr_src = rest[:comma_idx]
    after = rest[comma_idx+1:]
    # expect: optional spaces, 'x', optional spaces, ')', optional spaces,
    # optional '#' comment, end of string
    m = re.match(r"\s*x\s*\)\s*(#.*)?$", after)
    if not m:
        return None
    if not expr_src.strip():
        return None
    return expr_src


def rational_to_str(r):
    r = Rational(r)
    if r.q == 1:
        return str(int(r.p))
    return "%d/%d" % (r.p, r.q)


def process_case(expr_src):
    tokens = tokenize(expr_src)
    if not tokens:
        raise ParseError("empty expression")
    parser = Parser(tokens)
    expr = parser.parse_expr()
    if parser.i != len(parser.toks):
        raise ParseError("trailing tokens")
    expr = expr.expand()
    if expr.has(X) is False and expr == 0:
        raise ParseError("zero polynomial not allowed")
    poly = Poly(expr, X, domain='QQ')
    coeffs = [rational_to_str(c) for c in poly.all_coeffs()]

    ground = poly.ground_roots()  # dict root(Rational) -> multiplicity
    root_items = []
    for root, mult in ground.items():
        root_items.append((Rational(root), int(mult)))
    root_items.sort(key=lambda t: t[0])

    divisor = Poly(1, X, domain='QQ')
    for root, mult in root_items:
        divisor = divisor * Poly(X - root, X, domain='QQ') ** mult

    if root_items:
        quotient, remainder = sympy_div(poly, divisor, X, domain='QQ')
        if not remainder.is_zero:
            raise ParseError("exact division failed")
        residual_coeffs = [rational_to_str(c) for c in quotient.all_coeffs()]
    else:
        residual_coeffs = list(coeffs)

    rational_roots = [
        {"root": rational_to_str(root), "multiplicity": mult}
        for root, mult in root_items
    ]

    return {
        "coefficients": coeffs,
        "rational_roots": rational_roots,
        "residual_coefficients": residual_coeffs,
    }


def main():
    if len(sys.argv) != 2:
        print("usage: roots.py <path-to-markdown>", file=sys.stderr)
        sys.exit(2)
    path = sys.argv[1]
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()

    cases = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped.startswith("roots("):
            continue
        expr_src = find_roots_call(stripped)
        if expr_src is None:
            continue
        case = process_case(expr_src)
        cases.append(case)

    sys.stdout.write(json.dumps({"cases": cases}) + "\n")


if __name__ == "__main__":
    main()
