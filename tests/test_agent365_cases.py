"""Offline regression models of real, source-linked enterprise workflows."""
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlparse

import pytest

ROOT = Path(__file__).resolve().parent.parent / "examples" / "agent365-cases"
SPEC = importlib.util.spec_from_file_location("agent365_case_runner", ROOT / "run_cases.py")
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
CASES = sorted(path.parent for path in ROOT.glob("*/case.json"))


def test_exactly_ten_distinct_source_linked_case_folders():
    assert len(CASES) == 10
    titles = set()
    for folder in CASES:
        metadata = json.loads((folder / "case.json").read_text(encoding="utf-8"))
        assert folder.name == metadata["id"]
        titles.add(metadata["title"])
        assert metadata["sources"]
        assert metadata["published_facts"] and metadata["local_assumptions"]
        assert metadata["limitations"] and metadata["a365_relationship"]
        for source in metadata["sources"]:
            url = urlparse(source["url"])
            assert url.scheme == "https" and url.netloc
            assert source["title"] and source["retrieved_at"] and source["verification"]
        for name in ("README.md", "intent.md", "intent.json", "environment.json", "checks.json"):
            assert (folder / name).is_file()
    assert len(titles) == 10


@pytest.mark.parametrize("folder", CASES, ids=lambda path: path.name)
def test_real_case_model_and_runtime_counterexamples(folder, tmp_path):
    result = RUNNER.run_case(folder, tmp_path)
    assert result["live_customer_calls"] == 0
    assert len(result["checks"]) >= 12
    assert result["passed"], [
        item for item in result["checks"] if not item["passed"]]
    runtime = [item for item in result["checks"] if item["kind"] == "runtime"]
    assert sum(item["actual"]["transport_invocations"] for item in runtime) == 1


@pytest.mark.parametrize("folder", CASES, ids=lambda path: path.name)
def test_requirements_and_environment_evidence_are_separate(folder):
    intent = json.loads((folder / "intent.json").read_text(encoding="utf-8"))
    environment = json.loads((folder / "environment.json").read_text(encoding="utf-8"))
    assert "init_true" not in intent
    assert all(set(cap) == {"owner"} for cap in intent["capabilities"].values())
    assert set(environment["contracts"]) == set(intent["capabilities"])
    assert set(environment["grants"]) == set(intent["capabilities"])
    assert isinstance(environment["init_true"], list)
