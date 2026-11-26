"""Replay exact rational-root reports against an independent arithmetic oracle."""
import ast
import hashlib
import json
import math
import re
from fractions import Fraction
from itertools import zip_longest

from scripts.real_skills_runtime import Sandbox
from scripts.real_skills_verifiers import _unique_fields, _verify_json

SYMBOLIC = "k-dense-ai__claude-scientific-skills__sympy"
SYMBOLIC_IMAGE = "sha256:f2463a5fb589082083e77150379cc2c26f5998175cb27b1953ecd0e4245026cf"
ROOT_CALL = re.compile(r"roots\(([^,\n]+),\s*x\)\s*(?:#.*)?")


def _normal(values: list[Fraction]) -> list[Fraction]:
    while len(values) > 1 and values[-1] == 0:
        values.pop()
    if len(values) > 9 or any(max(v.numerator.bit_length(), v.denominator.bit_length()) > 128
                              for v in values):
        raise ValueError("Polynomial exceeds the degree-eight or bounded-arithmetic contract")
    return values


def _multiply(left: list[Fraction], right: list[Fraction]) -> list[Fraction]:
    result = [Fraction(0)] * (len(left) + len(right) - 1)
    for i, a in enumerate(left):
        for j, b in enumerate(right):
            result[i + j] += a * b
    return _normal(result)


def _polynomial(node: ast.AST) -> list[Fraction]:
    if isinstance(node, ast.Constant) and type(node.value) is int and abs(node.value) <= 1000000:
        return [Fraction(node.value)]
    if isinstance(node, ast.Name) and node.id == "x":
        return [Fraction(0), Fraction(1)]
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        sign = -1 if isinstance(node.op, ast.USub) else 1
        return [sign * value for value in _polynomial(node.operand)]
    if not isinstance(node, ast.BinOp):
        raise ValueError("Only bounded integer arithmetic and the polynomial symbol x are supported")
    left = _polynomial(node.left)
    if isinstance(node.op, ast.Pow):
        if (not isinstance(node.right, ast.Constant) or type(node.right.value) is not int
                or not 0 <= node.right.value <= 8):
            raise ValueError("Polynomial powers must be literal integers from zero through eight")
        result = [Fraction(1)]
        for _ in range(node.right.value):
            result = _multiply(result, left)
        return result
    right = _polynomial(node.right)
    if isinstance(node.op, (ast.Add, ast.Sub)):
        sign = -1 if isinstance(node.op, ast.Sub) else 1
        return _normal([a + sign * b for a, b in zip_longest(left, right, fillvalue=Fraction(0))])
    if isinstance(node.op, ast.Mult):
        return _multiply(left, right)
    if isinstance(node.op, ast.Div) and len(right) == 1 and right[0]:
        return _normal([a / right[0] for a in left])
    raise ValueError("Unsupported polynomial operator or nonconstant/zero divisor")


def _rational_factors(polynomial: list[Fraction]) -> tuple[dict[Fraction, int], list[Fraction]]:
    remainder = polynomial.copy()
    roots: dict[Fraction, int] = {}
    while len(remainder) > 1 and remainder[0] == 0:
        roots[Fraction(0)] = roots.get(Fraction(0), 0) + 1
        remainder = remainder[1:]
    if len(remainder) == 1:
        return roots, remainder
    scale = math.lcm(*(c.denominator for c in remainder))
    integers = [int(c * scale) for c in remainder]
    content = math.gcd(*integers)
    integers = [c // content for c in integers]
    if max(map(abs, integers)) > 1000000:
        raise ValueError("Primitive integer coefficients exceed one million")

    def divisors(number: int) -> set[int]:
        return {value for i in range(1, math.isqrt(number) + 1) if number % i == 0
                for value in (i, number // i)}

    candidates = {sign * Fraction(p, q) for p in divisors(abs(integers[0]))
                  for q in divisors(abs(integers[-1])) for sign in (-1, 1)}
    for root in sorted(candidates):
        while len(remainder) > 1:
            value = Fraction(0)
            for coefficient in reversed(remainder):
                value = value * root + coefficient
            if value:
                break
            quotient = [Fraction(0)] * (len(remainder) - 1)
            quotient[-1] = remainder[-1]
            for i in range(len(remainder) - 2, 0, -1):
                quotient[i - 1] = remainder[i] + root * quotient[i]
            assert remainder[0] + root * quotient[0] == 0
            remainder = quotient
            roots[root] = roots.get(root, 0) + 1
    return roots, remainder


def symbolic_reference(raw: bytes) -> dict:
    if len(raw) > 65536:
        raise ValueError("Symbolic input exceeds 65536 bytes")
    cases = []
    for line in raw.decode("utf-8").splitlines():
        if not line.strip().startswith("roots("):
            continue
        match = ROOT_CALL.fullmatch(line.strip())
        if not match or len(match[1]) > 512:
            raise ValueError("Expected a bounded single-line roots(expression, x) example")
        try:
            polynomial = _polynomial(ast.parse(match[1].strip(), mode="eval").body)
        except (SyntaxError, RecursionError) as error:
            raise ValueError("Invalid bounded polynomial expression") from error
        if polynomial == [0]:
            raise ValueError("The zero polynomial has infinitely many roots")
        roots, remainder = _rational_factors(polynomial)
        cases.append({
            "coefficients": [str(c) for c in reversed(polynomial)],
            "rational_roots": [{"root": str(root), "multiplicity": count}
                               for root, count in sorted(roots.items())],
            "residual_coefficients": [str(c) for c in reversed(remainder)],
        })
        if len(cases) > 32:
            raise ValueError("Symbolic document exceeds 32 examples")
    return {"cases": cases}


def symbolic_replays(raw: bytes) -> dict[str, bytes]:
    symbolic_reference(raw)
    lines = raw.decode("utf-8").splitlines()
    matches = [i for i, line in enumerate(lines) if ROOT_CALL.fullmatch(line.strip())]
    if len(matches) != 1:
        raise ValueError("Expected the unchanged public guide's single polynomial-root example")
    index, = matches
    changed = lines.copy()
    changed[index] = "\n".join([
        "roots((2*x - 1)**2*(3*x + 2)*(x**2 + 1), x)",
        "roots(x**4 - 2*x**2 + 1, x)",
        "roots(x**2/2 - 5*x/6 + 1/3, x)",
        "roots(7, x)", "roots(x**2 + 1, x)",
    ])
    empty = lines.copy()
    empty[index] = ""
    return {"core-capabilities.md": raw,
            "changed.md": ("\n".join(changed) + "\n").encode(),
            "no-examples.md": ("\n".join(empty) + "\n").encode()}


def verify_symbolic_roots(inputs: dict[str, bytes], actual: bytes, host: str) -> dict:
    if set(inputs) != {"core-capabilities.md"}:
        raise ValueError("Symbolic verification requires the unchanged public capability guide")
    variants = symbolic_replays(inputs["core-capabilities.md"])
    expected = {name: symbolic_reference(raw) for name, raw in variants.items()}
    identity = {"kind": "public_symbolic_rational_root_program_replay",
                "actual_sha256": hashlib.sha256(actual).hexdigest(),
                "general_symbolic_mathematics_verified": False}
    try:
        if len(actual) > 32768:
            raise ValueError("Symbolic program exceeds 32768 bytes")
        ast.parse(actual.decode("utf-8"))
    except (ValueError, SyntaxError, RecursionError) as error:
        return {**identity, "passed": False, "error": str(error)}
    sandbox = Sandbox(host, image=SYMBOLIC_IMAGE, site_packages=True)
    rows = []
    try:
        sandbox.start({**variants, "solver.py": actual}, [])
        for name in variants:
            worker = (
                "import json,subprocess,sys,time\n"
                f"name={name!r}\nstarted=time.monotonic()\n"
                "try:\n"
                " p=subprocess.run([sys.executable,'-I','-B','/inputs/solver.py',"
                "'/inputs/'+name],capture_output=True,text=True,timeout=15)\n"
                " row={'name':name,'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr}\n"
                "except subprocess.TimeoutExpired:\n"
                " row={'name':name,'error':'Symbolic solver exceeded fifteen-second replay limit'}\n"
                "row['seconds']=time.monotonic()-started\nprint(json.dumps(row,allow_nan=False))\n"
            )
            result = sandbox.execute(worker)
            if result["status"] != "completed" or result["exit_code"] != 0:
                return {**identity, "passed": False, "error": "Symbolic program replay failed", "runtime": result}
            try:
                row = json.loads(result["output"], object_pairs_hook=_unique_fields)
            except (ValueError, RecursionError) as error:
                return {**identity, "passed": False, "error": f"Invalid replay output: {error}"}
            if not isinstance(row, dict):
                return {**identity, "passed": False, "error": "Expected one symbolic replay result"}
            rows.append(row)
    finally:
        sandbox.stop()
    try:
        if len(rows) != len(expected):
            raise ValueError("Incomplete symbolic replay results")
        for row, (name, report) in zip(rows, expected.items(), strict=True):
            if row.get("name") != name or "error" in row:
                raise ValueError(f"Symbolic replay failed for {name}: {row.get('error', 'wrong input')}")
            checked = _verify_json(report, row["stdout"].encode(), "symbolic_rational_roots")
            if row["exit_code"] != 0 or row["stderr"] or not checked["passed"]:
                raise ValueError(f"Exact rational-root report or exit status differs for {name}")
    except (ValueError, RecursionError) as error:
        return {**identity, "passed": False, "error": str(error), "observed": rows}
    return {**identity, "passed": True, "checks": len(variants), "observed": rows,
            "cli_replay_timeout_seconds": 15,
            "replay_inputs_sha256": {name: hashlib.sha256(raw).hexdigest()
                                     for name, raw in variants.items()},
            "expected_sha256": hashlib.sha256(json.dumps(expected, sort_keys=True).encode()).hexdigest()}
