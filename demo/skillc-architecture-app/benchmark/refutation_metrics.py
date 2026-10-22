"""Refutation confusion matrix (positive = IMPOSSIBLE) with Wilson intervals.

Follows skillc.evaluate.refutation_metrics: rates are over labelled, decided
rows (ACHIEVABLE / IMPOSSIBLE truth and prediction); UNKNOWN predictions are
counted separately so abstentions are visible, and recall is also reported over
every labelled IMPOSSIBLE row so abstentions cannot hide misses.
"""
from __future__ import annotations

import math

LABELS = ("ACHIEVABLE", "IMPOSSIBLE")


def wilson(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    """95% Wilson score interval for a proportion, or None when total is 0."""
    if not total:
        return None
    p = successes / total
    centre = (p + z * z / (2 * total)) / (1 + z * z / total)
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / (1 + z * z / total)
    return [round(max(0.0, centre - half), 3), round(min(1.0, centre + half), 3)]


def rate(successes: int, total: int) -> dict:
    return {
        "value": round(successes / total, 3) if total else None,
        "n": total,
        "ci95": wilson(successes, total),
    }


def confusion(rows: list[dict]) -> dict:
    labelled = [r for r in rows if r["expected"] in LABELS]
    decided = [r for r in labelled if r["observed"] in LABELS]

    def count(expected: str, observed: str) -> int:
        return sum(r["expected"] == expected and r["observed"] == observed for r in decided)

    tp, fp = count("IMPOSSIBLE", "IMPOSSIBLE"), count("ACHIEVABLE", "IMPOSSIBLE")
    fn, tn = count("IMPOSSIBLE", "ACHIEVABLE"), count("ACHIEVABLE", "ACHIEVABLE")
    actual_impossible = sum(r["expected"] == "IMPOSSIBLE" for r in labelled)
    return {
        "positive_class": "IMPOSSIBLE",
        "labelled": len(labelled),
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "unknown_on_achievable": sum(r["expected"] == "ACHIEVABLE" and r["observed"] == "UNKNOWN"
                                     for r in labelled),
        "unknown_on_impossible": sum(r["expected"] == "IMPOSSIBLE" and r["observed"] == "UNKNOWN"
                                     for r in labelled),
        "false_positive_rate": rate(fp, fp + tn),
        "precision": rate(tp, tp + fp),
        "recall_decided": rate(tp, tp + fn),
        "recall_all_labelled_impossible": rate(tp, actual_impossible),
        "accuracy_decided": rate(tp + tn, len(decided)),
        "coverage": rate(len(decided), len(labelled)),
        "false_positive_ids": [r["id"] for r in decided
                               if r["expected"] == "ACHIEVABLE" and r["observed"] == "IMPOSSIBLE"],
    }
