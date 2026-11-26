import json
import os
import subprocess
from pathlib import Path

import pytest

from scripts.real_skills_symbolic import symbolic_reference, symbolic_replays, verify_symbolic_roots

SOLVER = b"""
import json,re,sys
from pathlib import Path
import sympy as sp
x=sp.Symbol('x')
cases=[]
for line in Path(sys.argv[1]).read_text().splitlines():
    match=re.fullmatch(r'roots\\(([^,\\n]+),\\s*x\\)\\s*(?:#.*)?',line.strip())
    if not match:
        continue
    poly=sp.Poly(sp.sympify(match[1],locals={'x':x}),x,domain=sp.QQ)
    roots=poly.ground_roots()
    remainder=poly
    for root,count in roots.items():
        remainder=sp.div(remainder,sp.Poly((x-root)**count,x,domain=sp.QQ))[0]
    cases.append({'coefficients':[str(c) for c in poly.all_coeffs()],
        'rational_roots':[{'root':str(r),'multiplicity':int(n)} for r,n in sorted(roots.items())],
        'residual_coefficients':[str(c) for c in remainder.all_coeffs()]})
print(json.dumps({'cases':cases}))
"""


def test_exact_rational_roots_multiplicities_and_unfactored_residual():
    report = symbolic_reference(b"roots((2*x-1)**2*(3*x+2)*(x**2+1), x)\n")
    assert report == {"cases": [{
        "coefficients": ["12", "-4", "7", "-2", "-5", "2"],
        "rational_roots": [{"root": "-2/3", "multiplicity": 1},
                           {"root": "1/2", "multiplicity": 2}],
        "residual_coefficients": ["12", "0", "12"],
    }]}


def test_zero_roots_rational_coefficients_constants_and_case_order():
    report = symbolic_reference(
        b"# data\nroots( x**3-6*x**2+9*x , x) # original\n"
        b"roots(x**2/2-5*x/6+1/3, x)\nroots(7, x)\nroots(x**2+1, x)\n")
    a, b, c, d = report["cases"]
    assert a["rational_roots"] == [{"root": "0", "multiplicity": 1},
                                   {"root": "3", "multiplicity": 2}]
    assert a["residual_coefficients"] == ["1"]
    assert b == {"coefficients": ["1/2", "-5/6", "1/3"],
                 "rational_roots": [{"root": "2/3", "multiplicity": 1},
                                    {"root": "1", "multiplicity": 1}],
                 "residual_coefficients": ["1/2"]}
    assert c == {"coefficients": ["7"], "rational_roots": [], "residual_coefficients": ["7"]}
    assert d["rational_roots"] == [] and d["residual_coefficients"] == ["1", "0", "1"]


@pytest.mark.parametrize("expression", [
    "x-x", "y+1", "True", "x**9", "x**-1", "x/0", "x/(x+1)",
    "__import__('os')", "x%2", "1000001*x+1",
])
def test_reference_rejects_nonpolynomial_unbounded_or_executable_input(expression):
    with pytest.raises(ValueError):
        symbolic_reference(f"roots({expression}, x)\n".encode())


def test_changed_and_empty_document_replays_do_not_restate_original_answer():
    original = b"# public guide\nroots(x**3-6*x**2+9*x, x) # original\n"
    variants = symbolic_replays(original)
    assert variants["core-capabilities.md"] == original
    assert len(symbolic_reference(variants["changed.md"])["cases"]) == 5
    assert symbolic_reference(variants["no-examples.md"]) == {"cases": []}


def test_verifier_rejects_hardcoded_and_mistyped_answers(monkeypatch):
    import scripts.real_skills_symbolic as symbolic

    original = b"roots(x**3-6*x**2+9*x, x)\n"
    expected = {name: symbolic_reference(raw) for name, raw in symbolic_replays(original).items()}
    rows = [{"name": name, "exit_code": 0, "stderr": "", "stdout": json.dumps(report)}
            for name, report in expected.items()]

    class Workspace:
        def __init__(self, host, **kwargs):
            assert kwargs == {"image": symbolic.SYMBOLIC_IMAGE, "site_packages": True}

        def start(self, inputs, writable):
            assert "solver.py" in inputs and not writable

        def execute(self, code):
            row = next(row for row in rows if repr(row["name"]) in code)
            return {"status": "completed", "exit_code": 0, "output": json.dumps(row)}

        def stop(self):
            pass

    monkeypatch.setattr(symbolic, "Sandbox", Workspace)
    assert verify_symbolic_roots({"core-capabilities.md": original}, b"pass", "unused")["passed"]
    rows[1]["stdout"] = rows[0]["stdout"]
    assert not verify_symbolic_roots({"core-capabilities.md": original}, b"pass", "unused")["passed"]
    rows[1]["stdout"] = json.dumps(expected["changed.md"])
    wrong = json.loads(rows[0]["stdout"])
    wrong["cases"][0]["rational_roots"][0]["multiplicity"] = True
    rows[0]["stdout"] = json.dumps(wrong)
    assert not verify_symbolic_roots({"core-capabilities.md": original}, b"pass", "unused")["passed"]


@pytest.mark.parametrize("hardcoded", [False, True])
def test_actual_symbolic_program_replays_and_rejects_fixed_answers(hardcoded):
    from scripts.real_skills_symbolic import SYMBOLIC, SYMBOLIC_IMAGE

    if os.environ.get("SKILLC_LOCAL_DOCKER") != "1":
        pytest.skip("Requires explicit isolated local Docker opt-in")
    assert os.environ.get("SKILLC_SYMBOLIC_IMAGE") == SYMBOLIC_IMAGE
    original = (Path(__file__).resolve().parents[1] / "runs" / "20261106_real_skills"
                / "reviewed-symbolic" / SYMBOLIC / "core-capabilities.md").read_bytes()
    program = ("print(" + repr(json.dumps(symbolic_reference(original))) + ")").encode() if hardcoded else SOLVER
    host = subprocess.check_output(
        ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
        text=True).strip()
    result = verify_symbolic_roots({"core-capabilities.md": original}, program, host)
    assert result["passed"] is not hardcoded, result
    if not hardcoded:
        assert result["checks"] == 3
