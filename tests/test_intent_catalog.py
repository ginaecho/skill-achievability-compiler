import importlib.util
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "demo" / "skillc-architecture-app"
sys.path.insert(0, str(APP))
SPEC = importlib.util.spec_from_file_location("intent_catalog", APP / "intent_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FORMS = {
    "SKILL.md": "---\nname: pay\n---\nUse `pay` to settle the invoice.",
    "agent.md": "---\nname: payer\ntools: [pay]\n---\nYou are the payer. Run `pay`.",
    "prompt.md": "Please settle my invoice with `pay`.",
}


def _topic(root: Path, topic_id: str = "pay_invoice") -> None:
    folder = root / "corpus" / "intents" / topic_id
    folder.mkdir(parents=True)
    (folder / "topic.json").write_text(json.dumps({
        "id": topic_id, "title": "Pay an invoice", "category": "ACHIEVABLE",
        "expected": "ACHIEVABLE", "required_tools": ["pay"],
    }))
    (folder / "environment.json").write_text(json.dumps({
        "name": "billing", "description": "A billing runtime.",
        "tools": {"pay": "settles the invoice"}, "grants": [], "lacks": [],
    }))
    for name, text in FORMS.items():
        (folder / name).write_text(text)


def test_case_name_removes_verdict_suffixes():
    assert MODULE._case_name("flight-booking-achievable") == "flight booking"
    assert MODULE._case_name("flight_booking_impossible") == "flight booking"
    assert MODULE._case_name("flight-booking") == "flight booking"


def test_topic_loads_three_distinct_native_forms_with_its_environment(tmp_path):
    _topic(tmp_path)
    read, list_topics = MODULE._worktree_reader(tmp_path)

    entries = MODULE._topic_entries(read, list_topics())

    assert [entry["input_type"] for entry in entries] == ["skill", "agent", "prompt"]
    assert {entry["base_id"] for entry in entries} == {"topic:pay_invoice"}
    assert [entry["content"] for entry in entries] == list(FORMS.values())
    assert all(entry["environment_grants"] == ["pay"] for entry in entries)
    assert all(entry["environment_manifest"]["name"] == "billing" for entry in entries)
    assert all("ACHIEVABLE" not in entry["name"] for entry in entries)
    assert entries[0]["display_category"] == "GENERAL CASE"


def test_real_artifacts_are_listed_only_in_their_own_form(tmp_path, monkeypatch):
    artifacts = [
        {"id": f"{kind}-{n}", "kind": kind, "pool": "p", "home_runtime": runtime,
         "repo_url": "https://github.com/o/r", "commit": "c" * 40,
         "path_in_repo": f"{kind}s/{kind}-{n}.md", "license_spdx": "MIT",
         "sha256": f"{kind}{n}", "content": f"{kind} {n}"}
        for kind, runtime in (("skill", "claude-code"), ("agent", "vscode-copilot"),
                              ("prompt", "vscode-copilot"))
        for n in range(2)
    ]
    monkeypatch.setattr(MODULE, "load_real_artifacts", lambda root: (artifacts, []))

    entries = MODULE._real_entries(tmp_path)

    assert len({entry["base_id"] for entry in entries}) == len(entries) == 6
    counts = {form: sum(e["input_type"] == form for e in entries) for form in MODULE.INPUT_FORMS}
    assert counts == {"skill": 2, "agent": 2, "prompt": 2}
    assert all(entry["environment_manifest"] is None for entry in entries)
    assert all(entry["form_provenance"] == "original upstream file" for entry in entries)
