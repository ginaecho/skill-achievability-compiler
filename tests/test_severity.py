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
