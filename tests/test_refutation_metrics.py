import importlib.util
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "demo" / "skillc-architecture-app"
sys.path.insert(0, str(APP))
SPEC = importlib.util.spec_from_file_location("refutation_metrics", APP / "refutation_metrics.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _row(expected, observed, i=0):
    return {"id": f"{expected}-{observed}-{i}", "expected": expected, "observed": observed}


def test_confusion_counts_and_rates_follow_impossible_as_positive():
    rows = ([_row("IMPOSSIBLE", "IMPOSSIBLE", i) for i in range(6)]
            + [_row("IMPOSSIBLE", "ACHIEVABLE")] + [_row("IMPOSSIBLE", "UNKNOWN")]
            + [_row("ACHIEVABLE", "ACHIEVABLE", i) for i in range(3)]
            + [_row("ACHIEVABLE", "IMPOSSIBLE")] + [_row("UNKNOWN", "IMPOSSIBLE")])

    m = MODULE.confusion(rows)

    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (6, 1, 1, 3)
    assert m["labelled"] == 12
    assert m["unknown_on_impossible"] == 1
    assert m["false_positive_rate"]["value"] == 0.25
    assert m["recall_all_labelled_impossible"]["value"] == 0.75
    assert m["false_positive_ids"] == ["ACHIEVABLE-IMPOSSIBLE-0"]


def test_wilson_interval_is_bounded_and_contains_the_estimate():
    low, high = MODULE.wilson(2, 21)
    assert 0 <= low < 2 / 21 < high <= 1
    assert MODULE.wilson(0, 0) is None
    assert MODULE.wilson(0, 10)[0] == 0.0
