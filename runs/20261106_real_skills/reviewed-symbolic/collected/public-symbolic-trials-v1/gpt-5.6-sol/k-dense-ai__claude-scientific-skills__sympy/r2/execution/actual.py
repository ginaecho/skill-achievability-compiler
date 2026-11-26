#!/usr/bin/env python3
import ast
import json
import sys

import sympy as sp

x = sp.Symbol("x")


def eval_math(node):
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, int):
            raise ValueError("integer literals only")
        return sp.Integer(node.value)
    if isinstance(node, ast.Name) and vars(node)["id"] == "x":
        return x
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = eval_math(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = eval_math(node.left)
        right = eval_math(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            if x in right.free_symbols or right == 0:
                raise ValueError("divisor must be a nonzero constant")
            return left / right
        if isinstance(node.op, ast.Pow):
            if (not isinstance(node.right, ast.Constant)
                    or isinstance(node.right.value, bool)
                    or not isinstance(node.right.value, int)
                    or not 0 <= node.right.value <= 8):
                raise ValueError("invalid power")
            return left ** node.right.value
    raise ValueError("unsupported expression")


def parse_case(line):
    tree = ast.parse(line.strip(), mode="eval")
    call = tree.body
    if (not isinstance(call, ast.Call)
            or not isinstance(call.func, ast.Name)
            or vars(call.func)["id"] != "roots"
            or len(call.args) != 2
            or call.keywords
            or not isinstance(call.args[1], ast.Name)
            or call.args[1].id != "x"):
        raise ValueError("invalid roots example")
    expression = eval_math(call.args[0])
    poly = sp.Poly(expression, x, domain=sp.QQ)
    if poly.is_zero:
        raise ValueError("polynomial must be nonzero")

    root_multiplicities = {}
    _, factors = poly.factor_list()
    residual = poly
    for factor, multiplicity in factors:
        if factor.degree() == 1:
            a, b = factor.all_coeffs()
            root = sp.Rational(-b, a)
            root_multiplicities[root] = root_multiplicities.get(root, 0) + multiplicity
            divisor = sp.Poly(x - root, x, domain=sp.QQ) ** multiplicity
            residual = residual.exquo(divisor)

    rational_roots = [
        {"root": rational_string(root), "multiplicity": int(root_multiplicities[root])}
        for root in sorted(root_multiplicities)
    ]
    return {
        "coefficients": [rational_string(c) for c in poly.all_coeffs()],
        "rational_roots": rational_roots,
        "residual_coefficients": [rational_string(c) for c in residual.all_coeffs()],
    }


def rational_string(value):
    value = sp.Rational(value)
    if value.q == 1:
        return str(value.p)
    return f"{value.p}/{value.q}"


def main():
    if len(sys.argv) != 2:
        raise SystemExit(2)
    with open(sys.argv[1], "r", encoding="utf-8") as source:
        cases = [parse_case(line) for line in source if line.strip().startswith("roots(")]
    sys.stdout.write(json.dumps({"cases": cases}, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
