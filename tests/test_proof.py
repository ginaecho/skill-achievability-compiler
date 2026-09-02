"""Type-check the mechanized soundness proof, when Coq is installed.

Locally (no coqc on PATH) these tests are skipped so ordinary `pytest` runs
stay green without a Coq toolchain. In the dedicated CI proof job, the
SKILLC_REQUIRE_COQ_PROOFS=1 environment variable is set, which turns a
missing coqc into a hard collection-time failure instead of a silent skip --
the mechanized proofs must actually be checked there, not bypassed.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

PROOF = Path(__file__).parent.parent / "proof"

_COQC = shutil.which("coqc")
_REQUIRE_COQ = os.environ.get("SKILLC_REQUIRE_COQ_PROOFS") == "1"

if _COQC is None and _REQUIRE_COQ:
    raise RuntimeError(
        "SKILLC_REQUIRE_COQ_PROOFS=1 but coqc was not found on PATH. "
        "The dedicated CI proof job must install a working Coq 8.18 "
        "toolchain -- refusing to silently skip the mechanized proofs."
    )

pytestmark = pytest.mark.skipif(_COQC is None, reason="coqc not installed")


def test_soundness_proof_typechecks(tmp_path):
    for src in ("SkillAchievability.v", "check_assumptions.v"):
        (tmp_path / src).write_text((PROOF / src).read_text())
    r = subprocess.run(["coqc", "SkillAchievability.v"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    r = subprocess.run(["coqc", "check_assumptions.v"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    # the axiom audit prints "Closed under the global context" for each theorem
    assert r.stdout.count("Closed under the global context") >= 3, r.stdout


def test_direct_typing_proof_typechecks(tmp_path):
    """The direct T-Comm/T-Act/T-Goal discipline (no local types, no
    projection, no merge, no separate subtyping relation): deadlock-freedom
    (progress), the head-move safety instance, and the labelled-LTS
    operational correspondence -- Subject Reduction and Session Fidelity with
    full communication interleaving (DirectTypingSR.v)."""
    for src in ("SkillAchievability.v", "DirectTyping.v", "DirectTypingSR.v",
                "check_direct_typing.v"):
        (tmp_path / src).write_text((PROOF / src).read_text())
    for src in ("SkillAchievability.v", "DirectTyping.v", "DirectTypingSR.v"):
        r = subprocess.run(["coqc", src], cwd=tmp_path,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
    r = subprocess.run(["coqc", "check_direct_typing.v"], cwd=tmp_path,
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.count("Closed under the global context") >= 9, r.stdout


def test_every_coq_result_the_paper_cites_exists_and_is_checked():
    """The paper's claim is not only that these theorems are proved but that
    all of them are `Print Assumptions` closed.  A citation naming a result no
    harness checks is a hole in that claim; a citation naming nothing at all
    is worse.  Both directions are checked here so the paper cannot drift
    away from the development between rounds."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "check_paper_citations.py"
    if not script.exists():
        import pytest
        pytest.skip("citation checker not present")
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_numbers_the_paper_states_match_the_shipped_results():
    """Two review rounds found stale figures in the evaluation -- right
    method, old run -- because nothing tied a sentence to the file it came
    from.  paper/WIP/results/CLAIMS.json ties them, and this fails when they
    drift.  It covers only what is mechanically derivable from a results
    file; the manifest says so rather than implying it covers the section."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "check_paper_numbers.py"
    if not script.exists():
        import pytest
        pytest.skip("numbers checker not present")
    r = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
