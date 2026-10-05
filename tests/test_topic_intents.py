"""Acceptance checks for topic intents in corpus/intents.

Each topic is one intent written natively three times (SKILL.md, agent.md,
prompt.md) plus the environment it is judged against. The intent files must
state requirements without revealing the verdict; environment facts belong in
environment.json only.
"""
import ast
import difflib
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOPICS = ROOT / "corpus" / "intents"
FORMS = ("SKILL.md", "agent.md", "prompt.md")
_SPEC = importlib.util.spec_from_file_location(
    "validate_topics", ROOT / "corpus" / "validate_topics.py")
VALIDATOR = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(VALIDATOR)
VERDICT_HINTS = VALIDATOR.VERDICT_HINTS
TOPIC_IDS = sorted(p.name for p in TOPICS.glob("*") if (p / "topic.json").is_file())
NEW_TOPIC_IDS = [
    t for t in TOPIC_IDS
    if "reference_pack" in json.loads((TOPICS / t / "topic.json").read_text(encoding="utf-8"))
]


def _reference_cases() -> dict:
    """build_corpus.py add/add_ext calls: id -> (capabilities, environment_grants)."""
    tree = ast.parse((ROOT / "corpus" / "build_corpus.py").read_text(encoding="utf-8"))
    cases = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") in {"add", "add_ext"}:
            case_id = ast.literal_eval(node.args[0])
            capabilities = set(ast.literal_eval(node.args[4])["capabilities"])
            grants = next(
                (set(ast.literal_eval(k.value)) for k in node.keywords
                 if k.arg == "environment_grants"),
                capabilities,
            )
            cases[case_id] = (capabilities, grants)
    return cases


REFERENCE = _reference_cases()


def _topic(topic_id: str) -> tuple[dict, dict, dict]:
    folder = TOPICS / topic_id
    topic = json.loads((folder / "topic.json").read_text(encoding="utf-8"))
    environment = json.loads((folder / "environment.json").read_text(encoding="utf-8"))
    forms = {name: (folder / name).read_text(encoding="utf-8") for name in FORMS}
    return topic, environment, forms


def test_original_thirty_two_topics_are_present():
    assert len(set(TOPIC_IDS) - set(NEW_TOPIC_IDS)) == 32


@pytest.mark.parametrize("topic_id", NEW_TOPIC_IDS)
def test_new_topic_label_matches_its_reference_pack(topic_id):
    pytest.importorskip("skillc.frontend.grants")
    assert VALIDATOR.problems(topic_id) == []


@pytest.mark.parametrize("topic_id", TOPIC_IDS)
def test_topic_metadata_is_complete(topic_id):
    topic, environment, _ = _topic(topic_id)
    assert topic["id"] == topic_id
    assert topic["expected"] in {"ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN", None}
    assert topic["required_tools"]
    assert isinstance(environment["tools"], dict)
    assert not [h for h in VERDICT_HINTS if h in topic["title"].lower()]


@pytest.mark.parametrize("topic_id", TOPIC_IDS)
def test_forms_are_distinct_native_texts(topic_id):
    _, _, forms = _topic(topic_id)
    texts = list(forms.values())
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            ratio = difflib.SequenceMatcher(None, texts[i], texts[j]).ratio()
            assert ratio < 0.6, f"{topic_id}: {FORMS[i]} and {FORMS[j]} are {ratio:.0%} alike"
    assert forms["SKILL.md"].startswith("---") and "allowed-tools" in forms["SKILL.md"]
    assert forms["agent.md"].startswith("---") and re.search(r"^tools:", forms["agent.md"], re.M)
    assert not forms["prompt.md"].startswith("---")


@pytest.mark.parametrize("topic_id", TOPIC_IDS)
def test_every_form_names_every_required_tool(topic_id):
    topic, _, forms = _topic(topic_id)
    for name, text in forms.items():
        absent = [tool for tool in topic["required_tools"] if f"`{tool}`" not in text]
        assert not absent, f"{topic_id}/{name} does not name {absent}"


@pytest.mark.parametrize("topic_id", TOPIC_IDS)
def test_intent_forms_do_not_reveal_the_verdict(topic_id):
    _, _, forms = _topic(topic_id)
    leaks = {
        name: hint for name, text in forms.items()
        for hint in VERDICT_HINTS if hint in text.lower()
    }
    assert not leaks, f"{topic_id}: {leaks}"


@pytest.mark.parametrize("topic_id", [t for t in TOPIC_IDS if t in REFERENCE])
def test_environment_withholds_as_many_tools_as_the_reference_case(topic_id):
    topic, environment, _ = _topic(topic_id)
    capabilities, grants = REFERENCE[topic_id]
    withheld = set(topic["required_tools"]) - set(environment["tools"])
    assert len(withheld) == len(capabilities - grants), (
        f"{topic_id}: environment withholds {sorted(withheld)}, "
        f"reference withholds {sorted(capabilities - grants)}"
    )
