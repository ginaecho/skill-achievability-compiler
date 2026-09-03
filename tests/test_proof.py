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
        # Some claims reach out of results/ (the shipped corpus, the hand
        # audit).  Copy whatever the manifest's own load() calls name.
        import re as _re
        for c in claims:
            for name in _re.findall(r"load\(\s*'([^']+)'", c["compute"]):
                src = (manifest.parent / name).resolve()
                if not src.is_file():
                    continue
                try:
                    rel = src.relative_to(root)
                except ValueError:
                    continue
                dst = tmp / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                if not dst.exists():
                    shutil.copy2(src, dst)
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


def _table_rows(tex: str, label: str):
    """The body rows of the table carrying \\label{label}, as cell lists."""
    block = tex.split("\\label{" + label + "}")[0].split("\\begin{tabular}")[-1]
    block = block.split("\\midrule", 1)[1].split("\\bottomrule")[0]
    block = block.replace("\\midrule", "")   # tab:use groups its rows
    out = []
    for line in block.strip().split("\\\\"):
        cells = [c.strip() for c in line.strip().split("&")]
        if len(cells) > 1:
            out.append(cells)
    return out


def test_the_severity_benchmark_table_matches_the_shipped_verdicts():
    """Table 1 is 17 rows x 6 figures and the numbers manifest reaches only
    its column totals.  A row could drift without any check noticing, so
    check every cell against results/severity.json."""
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    res, tex = root / "paper/WIP/results/severity.json", root / "paper/WIP/main.tex"
    if not (res.exists() and tex.exists()):
        import pytest
        pytest.skip("paper or results not present")

    data = {r["id"]: r for r in json.load(open(res))["rows"]
            if r.get("set") == "severity_benchmark"}
    rows = _table_rows(tex.read_text(encoding="utf-8"), "tab:bench")
    assert len(rows) == len(data) == 17, (len(rows), len(data))
    for cells in rows:
        name = re.sub(r"\s*\(.*\)", "", cells[0].replace("\\_", "_")).strip()
        r = data[name]
        assert (int(cells[2]), int(cells[3])) == (r["choices"], r["loops"]), name
        kstar, printed = r["k_star"], cells[5].replace("$\\ge$", ">=")
        if printed == ">=5":
            assert kstar is None or kstar >= 5, name
        else:
            assert kstar == int(printed), name
        counts = r["counts"]
        assert [int(c) for c in cells[6:9]] == [counts.get("Benign", 0),
                                                counts.get("Futile", 0),
                                                counts.get("Catastrophic", 0)], name


def test_the_modularity_table_matches_the_shipped_measurements():
    """Table 3's first column is the *complete* enumeration, not the plain
    whole-system run -- both are in the results and both appear in the
    paper, a few lines apart.  Pin each column to the field it came from."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    res, tex = root / "paper/WIP/results/severity.json", root / "paper/WIP/main.tex"
    if not (res.exists() and tex.exists()):
        import pytest
        pytest.skip("paper or results not present")

    mods = json.load(open(res))["modularity"]
    mig = {r["n"]: r for r in mods if r["family"] == "migration"}
    rows = _table_rows(tex.read_text(encoding="utf-8"), "tab:mod")
    assert len(rows) == 6, len(rows)
    for cells in rows:
        r = mig[int(cells[0])]
        assert [int(c) for c in cells[1:]] == [
            r["whole_system_complete"]["goal_queries"],
            r["whole_system_complete"]["exits"],
            r["modular"]["goal_queries"],
            r["modular"]["final_interface"],
            r["modular_projected"]["goal_queries"],
            r["modular_projected"]["final_interface"]], cells[0]


def test_the_usefulness_table_matches_the_shipped_runs():
    """Table 4's seven rows carry runs, outcomes, dollars and tokens; two of
    its figures were wrong until they were checked against the runs."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    res, tex = root / "paper/WIP/results/usefulness.json", root / "paper/WIP/main.tex"
    if not (res.exists() and tex.exists()):
        import pytest
        pytest.skip("paper or results not present")

    rows = json.load(open(res))["rows"]
    doc = lambda r: any(d in r["skill"] for d in ("/pdf/", "/xlsx/", "/docx/"))  # noqa: E731
    spec = lambda r: "spec-cases" in r["skill"]                                  # noqa: E731
    ref = lambda r: r["checker"].startswith("refuted")                           # noqa: E731
    groups = [
        lambda r: not ref(r) and r.get("size") is None and not spec(r),
        lambda r: ref(r) and r.get("size") is None and doc(r),
        lambda r: not ref(r) and "/A/" in r["skill"],
        lambda r: ref(r) and "/B/" in r["skill"],
        lambda r: ref(r) and r.get("size") is None and not doc(r) and not spec(r),
        lambda r: not ref(r) and r.get("size") is not None,
        lambda r: ref(r) and r.get("size") is not None,
    ]
    table = _table_rows(tex.read_text(encoding="utf-8"), "tab:use")
    assert len(table) == len(groups) == 7, len(table)
    for cells, keep in zip(table, groups):
        g = [r for r in rows if keep(r)]
        assert g, cells[0]
        assert int(cells[2]) == sum(r["runs"] for r in g), cells[0]
        # "20 (by hand)" in one row; the count is the leading integer.
        assert int(cells[3].split()[0]) == sum(r["success"] + r["verified_no_status"]
                                               for r in g), cells[0]
        assert int(cells[4]) == sum(r["silent_wrong"] for r in g), cells[0]
        assert int(cells[5]) == sum(r["honest_fail"] for r in g), cells[0]
        assert int(cells[6]) == sum(r["no_status"] for r in g), cells[0]
        usd = round(sum(r["cost_usd"] for r in g), 2)
        assert abs(float(cells[7].replace("\\$", "")) - usd) <= 0.005, (cells[0], usd)
        tok = sum(r["tokens"] for r in g) / 1e6
        assert abs(float(cells[8].split("\\")[0]) - tok) <= 0.005, (cells[0], tok)
