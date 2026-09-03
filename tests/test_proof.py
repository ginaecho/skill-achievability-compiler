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


def test_every_audited_name_is_a_proof_not_a_definition():
    """"N results, every one axiom-free" should count results.  A
    `Print Assumptions` on a Definition always prints "Closed under the global
    context" and proves nothing, so one in a harness inflates the number the
    paper reports."""
    import re
    from pathlib import Path

    proof = Path(__file__).resolve().parents[1] / "paper" / "WIP" / "proof"
    if not proof.is_dir():
        import pytest
        pytest.skip("proof directory not present")
    names = []
    for f in sorted(proof.glob("check_*.v")):
        names += re.findall(r"Print Assumptions\s+([A-Za-z0-9_']+)\s*\.", f.read_text())
    src = "\n".join(f.read_text() for f in sorted(proof.glob("*.v"))
                    if not f.stem.startswith("check_"))
    defs = [n for n in names
            if re.search(rf"^\s*(Definition|Fixpoint|Record|Inductive|CoInductive)\s+"
                         rf"{re.escape(n)}\b", src, re.M)]
    assert not defs, f"these audited names are definitions, not results: {defs}"
    # constructors are legitimate to audit -- the paper cites two rules by
    # name -- but they are not theorems, so the paper must not call them that
    ctors = [n for n in names
             if re.search(rf"^\s*\|\s*{re.escape(n)}\s*:", src, re.M)]
    tex = (Path(__file__).resolve().parents[1] / "paper" / "WIP" / "main.tex").read_text()
    assert f"({len(names) - len(ctors)} theorems and {len(ctors)} constructors" in tex, (
        f"{len(names)} audited names = {len(names) - len(ctors)} theorems + "
        f"{len(ctors)} constructors; the paper's supplement line disagrees")
    assert len(names) >= 150


def test_a_cited_phrase_leaving_the_prose_fails_the_numbers_check():
    """The manifest's job is to weld a sentence to the number it quotes.  It
    once did not: it compared data against data, so reverting the artifact
    README to a superseded figure left the suite green.  `cite` closed that,
    and this fails if the mechanism ever stops biting -- perturb a quoted
    phrase in a copy of the tree, and the checker must reject it."""
    import json
    import shutil
    import subprocess
    import sys
    import tempfile
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    script = root / "scripts" / "check_paper_numbers.py"
    manifest = root / "paper" / "WIP" / "results" / "CLAIMS.json"
    if not (script.exists() and manifest.exists()):
        import pytest
        pytest.skip("numbers checker not present")

    claims = json.loads(manifest.read_text())["claims"]
    cited = [(c["what"], cite) for c in claims for cite in c.get("cite", [])]
    assert cited, "no claim pins its wording; the manifest cannot guard prose"

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / "scripts").mkdir()
        shutil.copy2(script, tmp / "scripts" / script.name)
        shutil.copytree(manifest.parent, tmp / "paper" / "WIP" / "results")
        # One claim reaches out of results/ into the shipped corpus.
        data = root / "src" / "skillc" / "data"
        if data.is_dir():
            shutil.copytree(data, tmp / "src" / "skillc" / "data")
        for _, cite in cited:
            dst = tmp / cite["file"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if not dst.exists():
                shutil.copy2(root / cite["file"], dst)
        run = lambda: subprocess.run(                        # noqa: E731
            [sys.executable, str(tmp / "scripts" / script.name)],
            capture_output=True, text=True)

        assert run().returncode == 0, "the copied tree does not check out clean"

        what, cite = cited[0]
        target = tmp / cite["file"]
        text = target.read_text(encoding="utf-8")
        assert cite["text"] in " ".join(text.split())
        # Break the phrase without touching any number the manifest computes.
        target.write_text(text.replace(cite["text"].split()[0], "@@", 1),
                          encoding="utf-8")
        r = run()
        assert r.returncode == 1, "a cited phrase can leave the prose unnoticed"
        assert what in r.stdout, r.stdout + r.stderr
