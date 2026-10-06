"""Regression tests for the Copilot review findings on the eag-innovation PR."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from skillc import Verdict
from skillc.env import mcp
from skillc.env.model import Environment
from skillc.env.watch import LATEST, watch_once
from skillc.frontend.contracts import apply_contracts

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_report_cell_keeps_unknown_distinct_from_impossible():
    from scripts.make_report import verdict_cell

    assert verdict_cell(Verdict(achievable=False, unknown=True)) == "UNKNOWN"
    assert verdict_cell(Verdict(achievable=False, frontier=("x",))) == "IMPOSSIBLE (`x`)"
    assert verdict_cell(Verdict(achievable=True)) == "ACHIEVABLE"


def test_benchmark_verifier_fails_explicitly_not_by_assert(tmp_path):
    from scripts.verify_compaction_benchmark import VerificationError, verify

    (tmp_path / "frozen.json").write_text(json.dumps({"scenarios": []}))
    (tmp_path / "results.json").write_text(json.dumps([{"id": "x"}]))
    (tmp_path / "metrics.json").write_text("{}")
    (tmp_path / "calls.jsonl").write_text("")
    with pytest.raises(VerificationError):
        verify(tmp_path)
    assert not (tmp_path / "verification.json").exists()


def test_contracts_keep_an_ownerless_capability_ownerless():
    pack = {"name": "t", "roles": ["agent"],
            "capabilities": {"book": {"add": ["booked"]}},
            "protocol": [{"act": {"cap": "book", "by": "agent"}}], "goal": "booked"}

    binding = apply_contracts(pack, {"book": {"add": ["booked"]}}, {"booked": ""})

    assert binding.applied == ("book",)
    assert "owner" not in binding.pack["capabilities"]["book"]


def test_app_rejects_json_that_is_not_an_object():
    app_dir = ROOT / "demo" / "skillc-architecture-app"
    sys.path.insert(0, str(app_dir))
    app = _load("atlas_app_review", app_dir / "app.py")

    for body in (b"[]", b'"text"', b"3"):
        with pytest.raises(ValueError, match="JSON object"):
            app.parse_json_object(body)
    assert app.parse_json_object(b'{"a": 1}') == {"a": 1}


@pytest.mark.parametrize("config", [[], {"mcpServers": []}, {"projects": []},
                                    {"projects": {"p": []}}, {"servers": "x"}])
def test_malformed_mcp_config_is_recorded_as_unknown(tmp_path, config):
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps(config))

    env = mcp.probe([path])

    assert env.is_unknown(f"mcp_config:{path}")


@pytest.mark.parametrize("content", ["{not json", "[]", '{"schema": "other"}'])
def test_watch_repairs_an_invalid_latest_snapshot(tmp_path, content):
    (tmp_path / LATEST).write_text(content)

    report = watch_once(tmp_path, Environment, {})

    assert report["environment_changes"] is None
    Environment.load(tmp_path / LATEST)

def _catalog_module():
    app_dir = ROOT / "demo" / "skillc-architecture-app"
    sys.path.insert(0, str(app_dir))
    return _load("intent_catalog_review", app_dir / "intent_catalog.py")


def _git(cwd: Path, *args: str) -> None:
    import subprocess
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   cwd=cwd, check=True, capture_output=True)


def test_catalog_branch_reader_resolves_paths_from_a_vendored_subfolder(tmp_path):
    catalog = _catalog_module()
    vendored = tmp_path / "agentic-governance" / "skillc"
    topic = vendored / catalog.TOPICS_DIR / "pay"
    topic.mkdir(parents=True)
    (topic / "topic.json").write_text(json.dumps({"title": "Pay", "category": "C"}))
    (topic / "environment.json").write_text(json.dumps({"tools": {"pay": "pays"}}))
    for name in catalog.FORM_FILES.values():
        (topic / name).write_text(name)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "data")
    _git(tmp_path, "update-ref", f"refs/remotes/origin/{catalog.CATALOG_BRANCH}", "HEAD")

    read, list_topics = catalog._branch_reader(vendored)
    entries = catalog._topic_entries(read, list_topics())

    assert [entry["content"] for entry in entries] == list(catalog.FORM_FILES.values())


def test_catalog_without_data_branch_is_empty_with_a_hint(tmp_path):
    catalog = _catalog_module()
    _git(tmp_path, "init", "-q")

    result = catalog.load_catalog(tmp_path)

    assert result["count"] == 0
    assert "--catalog-root" in result["hint"]


def test_catalog_unreadable_topic_file_raises_a_clear_error(tmp_path):
    catalog = _catalog_module()
    read, _ = catalog._branch_reader(tmp_path)

    with pytest.raises(catalog.CatalogError, match="--catalog-root"):
        read("corpus/intents/missing/topic.json")


def test_mcp_snapshot_keeps_no_command_arguments_or_url_secrets(tmp_path):
    path = tmp_path / ".mcp.json"
    path.write_text(json.dumps({"mcpServers": {
        "local": {"command": "/usr/bin/npx", "args": ["server", "--api-key", "sk-SECRET"]},
        "remote": {"type": "http", "url": "https://user:pw@example.com/mcp?token=SECRET#x"},
    }}))

    env = mcp.probe([path])
    snapshot = json.dumps(env.to_dict())

    assert "SECRET" not in snapshot and "pw@" not in snapshot
    servers = {node["name"]: node["attrs"] for node in env.of_kind("mcp_server")}
    assert servers["local"]["command"] == "npx"
    assert servers["local"]["arg_count"] == 3
    assert servers["remote"]["url"] == "https://example.com/mcp"
