"""Severity analysis: the paper's worked instance and its repairs, checked
against the Coq development's verdicts (Severity.v: Gbad_is_0_tolerant,
Gbad_not_1_tolerant, Ggood_is_k_tolerant)."""
import json
from pathlib import Path

from skillc.severity import analyze, BENIGN, FUTILE, CATASTROPHIC

DATA = Path(__file__).resolve().parents[1] / "src" / "skillc" / "data"
BENCH = {e["id"]: e for e in json.load(open(DATA / "severity_corpus.json"))}


def test_booking_is_0_tolerant_not_1_tolerant():
    r = analyze(BENCH["booking_fastpath"]["pack"], kmax=3)
    assert r.tolerance_degree == 0
    assert r.pnr_action == "purchase"
    sev = {v.branch: v.severity for v in r.verdicts}
    assert sev["safe"] == BENIGN and sev["fast"] == CATASTROPHIC
    assert ("/choice@p#0", "fast") in r.narrowing


def test_repairs_restore_tolerance():
    for pid in ("booking_reordered", "booking_narrowed", "email_campaign_guarded"):
        r = analyze(BENCH[pid]["pack"], kmax=3)
        assert r.tolerance_degree is None, pid
        assert r.counts()[CATASTROPHIC] == 0, pid


def test_two_wrong_choices_needed():
    r = analyze(BENCH["migration_backup"]["pack"], kmax=3)
    assert r.tolerance_degree == 1
    assert r.pnr_action == "drop_old"


def test_severity_is_world_dependent():
    a = analyze(BENCH["claim_eligible"]["pack"], kmax=3)
    b = analyze(BENCH["claim_ineligible"]["pack"], kmax=3)
    assert a.tolerance_degree is None
    assert b.tolerance_degree == 0 and b.pnr_action == "refund"


def test_rollback_makes_deploy_reversible():
    with_rb = analyze(BENCH["deploy_with_rollback"]["pack"], kmax=3)
    without = analyze(BENCH["deploy_no_rollback"]["pack"], kmax=3)
    assert with_rb.tolerance_degree is None
    assert without.tolerance_degree == 0 and without.pnr_action == "deploy"


def test_benign_misselection_is_a_detour():
    r = analyze(BENCH["shipping_detour"]["pack"], kmax=3)
    mis = [v for v in r.verdicts if not v.intended]
    assert mis and all(v.severity == BENIGN for v in mis)
    assert r.tolerance_degree is None


def test_corpus_does_not_crash():
    for f in ("corpus.json", "corpus_extended.json"):
        for e in json.load(open(DATA / f)):
            analyze(e["pack"], kmax=2)


def test_cli_output_fits_a_paper_column(capsys):
    """The verbatim block in the paper is the tool's output: keep it narrow."""
    import json as _json
    import tempfile
    from skillc.cli import main
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        _json.dump(BENCH["migration_backup"]["pack"], fh)
    rc = main(["severity", fh.name])
    out = capsys.readouterr().out
    assert rc == 3                                   # k* finite
    assert "tolerance degree k* = 1" in out
    assert "PNR=drop_old" in out
    assert all(len(line) <= 78 for line in out.splitlines()), out


def test_live_agent_simulator_agrees_with_the_theorem():
    """A scripted (wrong-one-in-three) agent driven through the benchmark by
    the live-agent harness: a catastrophe needs more than k* misselections,
    and never happens on a protocol tolerant at every tested budget."""
    import random
    import sys
    sys.path.insert(0, str(DATA.parents[2] / "scripts"))
    from live_agents import simulate
    rng = random.Random(7)

    def chooser(labels, intended):
        bad = [l for l in labels if not intended[l]]
        good = [l for l in labels if intended[l]] or labels
        return rng.choice(bad) if bad and rng.random() < 0.34 else rng.choice(good)

    for pid, e in BENCH.items():
        k = analyze(e["pack"], kmax=4).tolerance_degree
        for seed in range(6):
            r = simulate(e, "scripted", "plain", seed, chooser)
            if r["outcome"] == "catastrophe":
                assert k is not None and r["misselections"] > k, (pid, r)


def test_bystander_check_flags_shared_variables():
    import json
    from skillc.severity import analyze
    d = {e["id"]: e["pack"] for e in json.load(open(DATA / "severity_corpus.json"))}
    audit = analyze(d["release_with_audit"], kmax=4).bystander
    cache = analyze(d["release_with_cache"], kmax=4).bystander
    assert audit["exact"] and audit["pairs"] > 0
    assert not cache["exact"]
    assert any("cache_warm" in c["reason"] for c in cache["conflicts"])


def test_verified_kernel_agrees_with_analyzer():
    import json, pytest
    from skillc.kernel import run_kernel, kernel_available
    from skillc.severity import analyze
    if not kernel_available():
        pytest.skip("verified kernel not built (make binary in paper/WIP/proof)")
    for e in json.load(open(DATA / "severity_corpus.json")):
        kr = run_kernel(e["pack"], kmax=4)
        if "skipped" in kr:
            continue
        assert kr["tolerance_degree"] == analyze(e["pack"], kmax=4).tolerance_degree, e["id"]


def test_spec_cases_are_certified_and_refuted_as_authored():
    from pathlib import Path
    from skillc.profiles import load_profile
    from skillc.frontend.markdown import compile_file
    from skillc.checker import check
    root = Path(__file__).resolve().parents[1] / "benchmarks" / "spec-cases"
    expected = {"order-in-budget": "GOAL_UNSAT", "publish-with-approval": "BLOCKED_GUARD",
                "onboard-badge": "GOAL_UNSAT", "ledger-verify": "MISSING_CAPABILITY",
                "quota-send": "GOAL_UNSAT", "migrate-with-quota": "GOAL_UNSAT",
                "sign-then-ship": "GOAL_UNSAT", "two-person-release": "BLOCKED_GUARD",
                "index-then-search": "BLOCKED_GUARD"}
    prof = load_profile("claude-code")
    for case, reason in expected.items():
        a = check(compile_file(root / case / "A" / "SKILL.md", prof).pack)
        b = check(compile_file(root / case / "B" / "SKILL.md", prof).pack)
        assert a.achievable, case
        assert not b.achievable and b.reason == reason, (case, b.reason)


def test_real_skills_flip_between_shell_and_no_shell_runtimes():
    import glob, pytest
    from pathlib import Path
    from skillc.profiles import load_profile
    from skillc.frontend.markdown import compile_file
    from skillc.checker import check
    root = Path(__file__).resolve().parents[1]
    files = sorted(glob.glob(str(root / "real-skills" / "**" / "SKILL.md"), recursive=True))
    if not files:
        pytest.skip("real-skills corpus not fetched (scripts/fetch_skills.py)")
    shell = load_profile("claude-ai"); noshell = load_profile("no-shell")   # claude-ai is these skills' home runtime
    flips = 0
    for f in files:
        a = check(compile_file(f, shell).pack)
        b = check(compile_file(f, noshell).pack)
        assert a.achievable, f                      # every skill runs in its home runtime
        if not b.achievable:
            assert b.reason == "MISSING_CAPABILITY"
            flips += 1
    assert flips >= 5                               # the code-fence rule makes the shell visible


def test_escalation_is_free_on_sound_refutations():
    """A refutation on the weak reading is sound whatever the document means,
    so it must never buy an LLM; a weak certification may."""
    from skillc.profiles import load_profile
    from skillc.frontend.markdown import compile_file
    from skillc.checker import check
    from skillc.autollm import needs_llm
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    f = root / "benchmarks" / "spec-cases" / "ledger-verify" / "B" / "SKILL.md"
    text = f.read_text()
    for prof in ("claude-code", "no-shell"):
        res = compile_file(f, load_profile(prof))
        v = check(res.pack)
        assert not v.achievable
        assert not needs_llm(text, res, v).needed


def test_analyzer_agrees_with_the_verified_kernel_on_random_protocols():
    """A miniature of scripts/differential_test.py: the hand-written analyzer
    and the Coq-extracted kernel share no code, so a disagreement on a random
    protocol is a defect in one of them."""
    import importlib.util, pytest
    from pathlib import Path
    from skillc.kernel import run_kernel, kernel_available
    from skillc.severity import analyze
    if not kernel_available():
        pytest.skip("kernel binary not built (make binary in paper/WIP/proof)")
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("difftest", root / "scripts" / "differential_test.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    import random
    rng = random.Random(99)
    for i in range(12):
        pack = mod.gen_pack(rng, i)
        k = run_kernel(pack, kmax=2)
        if "skipped" in k:
            continue
        assert k["tolerance_degree"] == analyze(pack, kmax=2).tolerance_degree, pack


def test_grep_baseline_is_weaker_than_the_checker():
    """Most of the corpus evaluation is a capability set-difference a regular
    expression can find; the specification cases are the ones that are not."""
    import importlib.util, json
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location("grepb", root / "scripts" / "grep_baseline.py")
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    res = json.load(open(root / "paper" / "WIP" / "results" / "grep_baseline.json"))
    assert res["checker_correct"] == res["n"]
    assert res["grep_correct"] < res["checker_correct"]
    # every case the grep misses is a refutation that needs reachability
    assert all(not r["truth"] for r in res["grep_wrong"])


def test_tolerance_degree_is_a_threshold_on_every_benchmark():
    """The tool-side counterpart of Severity.v's principal_characterises: k*
    is not merely where the scan stopped.  For every benchmark protocol with
    a finite tolerance degree, no hazard is affordable at any budget <= k*
    and one is affordable at every budget above it, up to kmax.  If that
    failed, computing k* by an increasing scan would be unsound."""
    from skillc.pack import Pack
    from skillc.severity import SeverityAnalyzer, initial_state

    KMAX = 4
    checked = 0
    for entry in BENCH.values():
        raw = entry["pack"]
        irreversible = raw.get("irreversible")
        pack = Pack.load({k: v for k, v in raw.items() if k != "irreversible"})
        rep = analyze(raw, kmax=KMAX)
        k = rep.tolerance_degree
        if k is None:                       # no hazard within kmax: nothing to test
            continue
        for b in range(0, KMAX + 1):
            an = SeverityAnalyzer(pack, kmax=KMAX, irreversible=irreversible)
            found, _, _ = an.hazard_within(list(pack.protocol), initial_state(pack),
                                           {}, b, set(), record=False)
            assert found == (b > k), (
                f"{entry['id']}: hazard within {b} misselections is {found}, "
                f"but k* = {k} says it should be {b > k}")
        checked += 1
    assert checked > 0, "no benchmark protocol had a finite tolerance degree"
