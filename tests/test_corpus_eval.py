"""The corpus evaluation as an executable claim: reproduces the paper's
confusion matrix and audits soundness (T1) / incompleteness (T3)."""
import json
from importlib import resources

from skillc import check
from skillc.evaluate import evaluate, format_report, load_corpus

EXPECTED_REASONS = {
    "hallucinated_email": "MISSING_CAPABILITY",
    "missing_tool_chain": "MISSING_CAPABILITY",
    "no_establisher": "GOAL_UNSAT",
    "two_goals_one_missing": "GOAL_UNSAT",
    "over_budget": "GOAL_UNSAT",
    "blocked_precondition": "BLOCKED_GUARD",
    "deadlock_unobserved": "NON_PROJECTABLE",
}


def test_confusion_matrix_matches_paper():
    res = evaluate()
    assert (res.tp, res.fn, res.fp, res.tn) == (6, 0, 2, 7)


def test_soundness_no_false_impossible():
    res = evaluate()
    assert res.sound, f"T1 violated: false IMPOSSIBLE on {res.fn_ids}"


def test_incompleteness_only_on_spurious_residue():
    corpus = load_corpus()
    res = evaluate(corpus)
    assert res.fp_all_spurious(corpus), (
        f"incompleteness audit failed: structural miss among {res.fp_ids}")
    assert sorted(res.fp_ids) == ["spurious_intent", "spurious_payload"]


def test_each_failure_mode_fires_its_matching_reason():
    packs = {c["id"]: c["pack"] for c in load_corpus()}
    for cid, expected in EXPECTED_REASONS.items():
        v = check(packs[cid])
        assert not v.achievable, cid
        assert v.reason == expected, (
            f"{cid}: expected {expected}, got {v.reason}")


def test_achievable_specs_have_witness_paths():
    for c in load_corpus():
        if c["ground_truth"] == "ACHIEVABLE":
            v = check(c["pack"])
            assert v.achievable and len(v.witness) > 0, c["id"]


# --------------------------------------------------------------------------
# UNKNOWN is an abstention: it never enters the confusion matrix
# --------------------------------------------------------------------------

def load_extended() -> list[dict]:
    data = resources.files("skillc").joinpath(
        "data/corpus_extended.json").read_text(encoding="utf-8")
    return json.loads(data)


def test_unknown_predictions_are_scored_as_abstentions():
    ext = load_extended()
    res = evaluate(ext)
    assert res.unknown == 1 and res.unknown_ids == ["spawn_helpers"]
    assert res.tp + res.tn + res.fp + res.fn == res.n - res.unknown
    assert res.n_scored == res.tp + res.tn + res.fp + res.fn


def test_unknown_is_never_a_soundness_violation():
    res = evaluate(load_extended())
    assert res.sound, f"UNKNOWN counted as a false IMPOSSIBLE: {res.fn_ids}"
    assert "spawn_helpers" not in res.fn_ids
    assert "spawn_helpers" not in res.fp_ids


def test_headline_corpus_has_no_abstentions():
    res = evaluate()
    assert res.unknown == 0 and res.n_scored == res.n


def test_report_states_the_abstentions_explicitly():
    ext = load_extended()
    out = format_report(evaluate(ext), ext)
    assert "UNKNOWN" in out and "spawn_helpers" in out
    assert "abstention" in out.lower()
