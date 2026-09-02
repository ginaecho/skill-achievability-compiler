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
