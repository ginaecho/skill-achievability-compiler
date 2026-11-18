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
    assert r.stdout.count("Closed under the global context") >= 8, r.stdout


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
    block = block.replace("\\midrule", "")   # a table may group its rows
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


def test_the_real_protocol_table_matches_the_shipped_results():
    """The real-protocol table is 18 rows x 11 figures, and the numbers
    manifest reaches only its totals.  Check every cell: roles from the pack,
    choices, k*, irreversible action and misselection counts from
    results/severity.json, and the two repaired k* from the repair summary."""
    import json
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    res, tex = root / "paper/WIP/results/severity.json", root / "paper/WIP/main.tex"
    rep = root / "benchmarks/severity_real/repairs_summary.json"
    if not (res.exists() and tex.exists() and rep.exists()):
        import pytest
        pytest.skip("paper or results not present")

    data = {r["id"]: r for r in json.load(open(res))["rows"] if r.get("set") == "severity_real"}
    repairs = {r["case"]: r for r in json.load(open(rep))}
    text = tex.read_text(encoding="utf-8")
    rows = _table_rows(text, "tab:real")
    assert len(rows) == len(data) == 18, (len(rows), len(data))
    seen = set()

    # the source is a group header above its rows, not a column: check that
    # every row sits under the header naming its source
    block = text.split("\\label{tab:real}")[0].split("\\begin{tabular}")[-1]
    header, under = None, {}
    for chunk in block.split("\\\\"):
        if "\\multicolumn" in chunk:
            header = chunk
        elif "&" in chunk and header is not None:
            under[chunk.strip().split("&")[0].strip().replace("\\_", "_")] = header
    expect = {"awesome-copilot": "awesome-copilot", "anthropics/skills": "Anthropic's skills",
              "tau airline": "airline policy, $\\tau$-bench", "tau2 airline": "$\\tau^2$-bench",
              "tau retail": "retail policy, $\\tau$-bench", "tau2 telecom": "telecom policy, $\\tau^2$-bench"}

    def k(printed, value):
        printed = printed.replace("$\\ge$", ">=")
        return value is None if printed == ">=5" else value == int(printed)

    # under a policy header the row drops the domain prefix of the protocol id
    prefix = {"airline policy": "airline_", "retail policy": "retail_", "telecom policy": "telecom_"}
    for cells in rows:
        short = cells[0].replace("\\_", "_")
        name = next((p + short for h, p in prefix.items() if h in under[short]), short)
        r, rp = data[name], repairs[name]
        pack = json.load(open(root / "benchmarks/severity_real" / name / "pack.json"))
        pack = pack.get("pack", pack)
        assert expect[rp["source"]] in under[short], name
        assert int(cells[1]) == len(pack["roles"]), name
        assert (int(cells[2]), int(cells[3])) == (r["choices"] - r["external_choices"],
                                                  r["external_choices"]), name
        assert cells[4].replace("\\_", "_") == r["irreversible_caps"][0], name
        assert k(cells[5], r["k_star"]), name
        m = r["misselections"]
        assert [int(c) for c in cells[6:9]] == [m["Benign"], m["Futile"], m["Catastrophic"]], name
        assert k(cells[9], rp["k_enforced"]) and k(cells[10], rp["k_narrowed"]), name
        assert rp["k_orig"] == r["k_star"], name
        seen.add(name)
    assert seen == set(data), set(data) - seen


def test_the_live_agent_table_matches_the_recorded_runs():
    """The live-agent table: every cell against the summary the manifest reads,
    and the catastrophe and goal columns also against the matrix that
    scripts/live_agents.py wrote independently from the same runs."""
    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    res = root / "paper/WIP/results"
    tex = root / "paper/WIP/main.tex"
    if not ((res / "live_agents_summary.json").exists() and tex.exists()):
        import pytest
        pytest.skip("paper or results not present")

    summary = json.load(open(res / "live_agents_summary.json"))
    cell = {(c["group"], c["cond"], c["arm"]): c for c in summary["cells"]}
    matrix = {(m["group"], m["cond"], m["arm"]): m for m in json.load(open(res / "live_agents.json"))["matrix"]}
    rows = _table_rows(tex.read_text(encoding="utf-8"), "tab:live")
    assert len(rows) == 10, len(rows)
    for cells in rows:
        g, c = cells[0], cells[1].replace("\\_", "_")
        u, t = cell[(g, c, "ungated")], cell[(g, c, "gated")]
        assert int(cells[2]) == u["runs"] == t["runs"], (g, c)
        assert [int(x) for x in cells[3:9]] == [u["entered_catastrophic"], t["entered_catastrophic"],
                                                u["catastrophes"], t["catastrophes"],
                                                u["success"], t["success"]], (g, c)
        for arm, x in (("ungated", u), ("gated", t)):
            m = matrix[(g, c, arm)]
            assert (m["runs"], m["catastrophe"], m["success"]) == (
                x["runs"], x["catastrophes"], x["success"]), (g, c, arm)


def test_the_live_agent_summary_is_current():
    """results/live_agents_summary.json is what the manifest reads; it must be
    what scripts/live_agents_summary.py computes from the shipped runs now."""
    import importlib.util
    import json
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    shipped = root / "paper/WIP/results/live_agents_summary.json"
    if not shipped.exists():
        import pytest
        pytest.skip("summary not present")
    sys.path.insert(0, str(root / "scripts"))
    spec = importlib.util.spec_from_file_location("las", root / "scripts" / "live_agents_summary.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fresh = json.loads(json.dumps(mod.build()))
    assert fresh == json.load(open(shipped))
