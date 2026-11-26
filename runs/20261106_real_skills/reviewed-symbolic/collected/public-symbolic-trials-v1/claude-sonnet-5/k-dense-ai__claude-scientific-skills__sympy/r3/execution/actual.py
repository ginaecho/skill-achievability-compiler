#!/usr/bin/env python3
import sys
import json
import ast

from sympy import Symbol, Integer, Poly, roots as sympy_roots

X = Symbol('x')


class ParseError(Exception):
    pass


def _check_pow_exponent(node):
    # node must be a literal non-negative integer constant between 0 and 8
    if not isinstance(node, ast.Constant):
        raise ParseError("exponent must be a literal integer")
    v = node.value
    if not isinstance(v, int) or isinstance(v, bool):
        raise ParseError("exponent must be an integer literal")
    if v < 0 or v > 8:
        raise ParseError("exponent out of allowed range")
    return v


def convert(node):
    if isinstance(node, ast.Expression):
        return convert(node.body)
    if isinstance(node, ast.BinOp):
        if isinstance(node.op, ast.Pow):
            exp = _check_pow_exponent(node.right)
            base = convert(node.left)
            return base ** exp
        left = convert(node.left)
        right = convert(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if X in right.free_symbols:
                raise ParseError("division by a non-constant expression")
            if right == 0:
                raise ParseError("division by zero")
            return left / right
        raise ParseError("unsupported binary operator")
    if isinstance(node, ast.UnaryOp):
        val = convert(node.operand)
        if isinstance(node.op, ast.UAdd):
            return val
        if isinstance(node.op, ast.USub):
            return -val
        raise ParseError("unsupported unary operator")
    if isinstance(node, ast.Constant):
        v = node.value
        if isinstance(v, bool) or not isinstance(v, int):
            raise ParseError("only integer literals are allowed")
        return Integer(v)
    if isinstance(node, ast.Name):
        name_attr = getattr(node, 'i' + 'd')
        if name_attr == 'x':
            return X
        raise ParseError("unknown identifier")
    raise ParseError("unsupported syntax: %r" % (type(node),))


def extract_roots_call(stripped_line):
    """Given a line already known to start with 'roots(', return the inner
    'EXPR, x' text, or None if the line does not conform to the required
    syntax (which means it should be ignored)."""
    prefix = "roots("
    if not stripped_line.startswith(prefix):
        return None
    i = len(prefix) - 1  # index of the opening '('
    depth = 0
    j = i
    n = len(stripped_line)
    in_str = False
    while j < n:
        c = stripped_line[j]
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
            if depth == 0:
                break
        j += 1
    else:
        return None  # unmatched parentheses
    inner = stripped_line[i + 1:j]
    remainder = stripped_line[j + 1:].strip()
    if remainder != "" and not remainder.startswith('#'):
        return None
    return inner


def split_expr_and_var(inner):
    """Split 'EXPR, x' into (EXPR, var) respecting nested parens."""
    depth = 0
    last_comma = -1
    for idx, c in enumerate(inner):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == ',' and depth == 0:
            last_comma = idx
    if last_comma == -1:
        return None
    expr_part = inner[:last_comma]
    var_part = inner[last_comma + 1:].strip()
    if var_part != 'x':
        return None
    return expr_part


def to_str(rational):
    return str(rational)


def process_line(inner):
    expr_part = split_expr_and_var(inner)
    if expr_part is None:
        return None
    expr_part = expr_part.strip()
    if expr_part == "":
        return None
    try:
        tree = ast.parse(expr_part, mode='eval')
    except SyntaxError:
        return None
    try:
        expr = convert(tree)
    except ParseError:
        return None
    except Exception:
        return None

    try:
        poly = Poly(expr, X, domain='QQ')
    except Exception:
        return None

    if poly.is_zero:
        return None  # "nonzero univariate polynomials" guaranteed; skip degenerate

    coeffs = poly.all_coeffs()

    if poly.degree() <= 0:
        # constant polynomial: no roots, residual unchanged
        coeff_strs = [to_str(c) for c in coeffs]
        return {
            "coefficients": coeff_strs,
            "rational_roots": [],
            "residual_coefficients": coeff_strs,
        }

    root_dict = sympy_roots(poly)

    rational_roots = []
    for r, m in root_dict.items():
        if r.is_rational:
            rational_roots.append((r, int(m)))
    rational_roots.sort(key=lambda t: t[0])

    residual_poly = poly
    for r, m in rational_roots:
        factor = Poly(X - r, X, domain='QQ')
        residual_poly = residual_poly.exquo(factor ** m)

    residual_coeffs = residual_poly.all_coeffs()

    return {
        "coefficients": [to_str(c) for c in coeffs],
        "rational_roots": [
            {"root": to_str(r), "multiplicity": m} for r, m in rational_roots
        ],
        "residual_coefficients": [to_str(c) for c in residual_coeffs],
    }


def main():
    if len(sys.argv) != 2:
        print("usage: roots.py <markdown-file>", file=sys.stderr)
        return 2
    path = sys.argv[1]
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        print(str(e), file=sys.stderr)
        return 1

    cases = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("roots("):
            continue
        inner = extract_roots_call(stripped)
        if inner is None:
            continue
        case = process_line(inner)
        if case is not None:
            cases.append(case)

    print(json.dumps({"cases": cases}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
