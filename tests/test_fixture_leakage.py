import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

VERDICT_HINTS = (
    "none of these tools",
    "no tool can",
    "there is no approval tool",
    "nothing in the plan",
    "classic freeze",
    "no ledger tool exists",
    "payload claim is false",
    "satisfies the formal goal but not",
    "either branch reaches the goal",
    "being ready for more",
    "what reaches the goal",
    "that completes the plan",
    "nothing establishes",
    "invokes a tool nobody has",
    "declared handler only handles one path",
    "extra external choices are safe",
)


def test_synthetic_inputs_do_not_explain_their_expected_verdicts():
    inputs = {
        str(path.relative_to(ROOT)): path.read_text(encoding="utf-8")
        for path in (ROOT / "corpus" / "skills").glob("*/SKILL.md")
    }
    for filename in ("corpus.json", "corpus_extended.json"):
        rows = json.loads((ROOT / "src" / "skillc" / "data" / filename).read_text())
        inputs.update({f"{filename}:{row['id']}": row["nl"] for row in rows})
    compaction = json.loads(
        (ROOT / "benchmark" / "compaction_cases.json").read_text(encoding="utf-8")
    )
    inputs.update({f"compaction:{row['id']}": row["task"] for row in compaction})

    leaks = {
        name: hint
        for name, text in inputs.items()
        for hint in VERDICT_HINTS
        if hint in text.lower()
    }
    assert not leaks


def test_environment_failures_keep_requirements_in_the_intent():
    rows = []
    for filename in ("corpus.json", "corpus_extended.json"):
        rows.extend(json.loads(
            (ROOT / "src" / "skillc" / "data" / filename).read_text()
        ))

    for row in rows:
        required = set(row["pack"]["capabilities"])
        granted = set(row["environment_grants"])
        unavailable = required - granted
        if not unavailable:
            continue
        source = row["nl"].lower()
        assert all(capability.lower() in source for capability in unavailable), (
            f"{row['id']} hides required capabilities from the intent: "
            f"{sorted(unavailable)}"
        )
