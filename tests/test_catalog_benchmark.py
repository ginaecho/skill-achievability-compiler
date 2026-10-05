import importlib.util
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "demo" / "skillc-architecture-app"
sys.path.insert(0, str(APP))
SPEC = importlib.util.spec_from_file_location("benchmark_catalog", APP / "benchmark_catalog.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _entry(content: str, grants: list[str]) -> dict:
    return {
        "id": "topic:t:prompt", "base_id": "topic:t", "name": "t", "suite": "Topics",
        "category": "C", "input_type": "prompt", "form_provenance": "authored",
        "source_path": "p", "expected": None, "environment_grants": grants,
        "content": content,
    }


def test_prompt_naming_a_granted_tool_is_not_refuted():
    row = MODULE.evaluate_entry(_entry("Please use `pay` to settle my invoice.", ["pay"]))

    assert row["observed"] == "ACHIEVABLE"


def test_prompt_naming_an_ungranted_tool_is_refuted_with_that_tool():
    row = MODULE.evaluate_entry(_entry("Please use `settle_invoice` to pay it.", ["read"]))

    assert (row["observed"], row["frontier"]) == ("IMPOSSIBLE", ["settle_invoice"])
