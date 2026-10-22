"""Classify MISSING_CAPABILITY refutations against hand-labelled frontier names."""
from __future__ import annotations

import json
from pathlib import Path

LABELS_PATH = Path(__file__).with_name("real-refutation-labels.json")
# Labels that do not confirm a refutation: not a tool, or a real built-in under
# a spelling the documented runtime profile does not list.
NON_CONFIRMING = {"misextraction", "runtime_name_variant"}


def load_labels(path: Path = LABELS_PATH) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {
        name.lower(): label
        for label, names in data["labels"].items()
        for name in names
    }


def classify(result: dict, real_tools: set[str], labels: dict[str, str]) -> str | None:
    """Return the audit status of one refutation, or None if not a refutation.

    A refutation is confirmed when at least one frontier name is a real tool the
    environment lacks; it is false when every frontier name is a misextraction.
    """
    if result["verdict"] != "IMPOSSIBLE":
        return None
    if result["reason"] != "MISSING_CAPABILITY":
        return "unaudited"
    statuses = {
        "absent_tool" if tool.lower() in real_tools else labels.get(tool.lower(), "unlabeled")
        for tool in map(str, result["frontier"])
    }
    if "absent_tool" in statuses:
        return "confirmed"
    if statuses <= NON_CONFIRMING:
        return "false_refutation"
    return "unlabeled"


def summarize(statuses: list[str | None]) -> dict:
    counts = {status: statuses.count(status)
              for status in ("confirmed", "false_refutation", "unlabeled", "unaudited")}
    decided = counts["confirmed"] + counts["false_refutation"]
    counts["precision"] = round(counts["confirmed"] / decided, 3) if decided else None
    return counts
