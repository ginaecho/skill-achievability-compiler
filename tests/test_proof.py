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
