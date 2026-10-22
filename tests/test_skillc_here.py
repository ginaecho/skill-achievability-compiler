"""demo/skillc-here: the environment tab and the graph tab, without the server."""
import importlib.util
from pathlib import Path

import pytest

from skillc.env import claude

MODULE_PATH = Path(__file__).resolve().parents[1] / "demo" / "skillc-here" / "app.py"
SPEC = importlib.util.spec_from_file_location("skillc_here_app", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


@pytest.fixture
def env(tmp_path):
    # no settings, MCP configs or credentials from this machine: the bundled tool list only
    return app.read_environment(refresh=True, probe=lambda: claude.probe(
        root=tmp_path, settings=(), mcp_configs=(), credentials=(), check_egress=False))


def _skill(name):
    return next(s["text"] for s in app.samples() if s["name"] == name)


def _verdicts(result):
    return {r["setting"]: (r["verdict"], r["missing"]) for r in result["rows"]}


def test_environment_lists_tools_and_grants(env):
    names = {t["name"] for t in env["tools"]}
    assert {"bash", "read", "edit"} <= names
    assert "bash" in env["grants"]
    assert env["credentials"] == []


def test_same_skill_differs_by_setting(env):
    v = _verdicts(app.check_skill(_skill("fix-failing-test"), app.settings(env)))
    assert v["claude.ai"] == ("IMPOSSIBLE", ["edit", "grep", "read"])
    assert v["Claude Code"][0] == "ACHIEVABLE"
    assert v["this machine"][0] == "ACHIEVABLE"
    v = _verdicts(app.check_skill(_skill("book-a-table"), app.settings(env)))
    assert v["claude.ai"][0] == "ACHIEVABLE"
    assert v["this machine"] == ("IMPOSSIBLE", ["ask_user_input_v0", "web_search"])


def test_what_if_changes_only_this_machine(env):
    where = app.settings(env)
    where["this machine"] = [*env["grants"], "slack_send_message"]
    v = _verdicts(app.check_skill(_skill("post-release-note"), where))
    assert v["Claude Code"] == ("IMPOSSIBLE", ["slack_send_message"])
    assert v["this machine"][0] == "ACHIEVABLE"


def test_free_prompt_abstains_rather_than_approves(env):
    v = _verdicts(app.check_skill("Book me a flight to Paris and email me the ticket.",
                                  app.settings(env)))
    assert {verdict for verdict, _ in v.values()} == {"UNKNOWN"}


def test_empty_or_oversized_text_is_refused(env):
    with pytest.raises(ValueError):
        app.check_skill("  ", app.settings(env))
    with pytest.raises(ValueError):
        app.check_skill("x" * (app.MAX_SKILL + 1), app.settings(env))


def test_graph_tab_explores_and_checks():
    pytest.importorskip("rdflib")
    data = app.GRAPH_EXAMPLE.read_bytes()
    text = app.twin_explore(app.GRAPH_EXAMPLE.name, data)["text"]
    assert "demo-building.trig" in text and "Temp" not in text.split("\n", 1)[0]
    out = app.twin_check(app.GRAPH_EXAMPLE.name, data, app.WORKFLOW_EXAMPLE.read_text("utf-8"))
    rows = {r["target"]: r for r in out["workflows"][0]["results"]}
    assert rows["ex:sp1"]["verdict"] == "ACHIEVABLE"
    assert "min_max_units" in rows["ex:sp2"]["missing"]


def test_graph_tab_refuses_jsonld_and_empty_workflow():
    with pytest.raises(ValueError, match="JSON-LD"):
        app.twin_explore("graph.jsonld", b"{}")
    with pytest.raises(ValueError):
        app.twin_check(app.GRAPH_EXAMPLE.name, app.GRAPH_EXAMPLE.read_bytes(), " ")
