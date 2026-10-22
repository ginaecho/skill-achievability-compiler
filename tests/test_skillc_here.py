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
    assert "campus-building.trig" in text and "Temp" not in text.split("\n", 1)[0]
    out = app.twin_check(app.GRAPH_SMALL.name, app.GRAPH_SMALL.read_bytes(),
                         app.WORKFLOW_EXAMPLE.read_text("utf-8"))
    rows = {r["target"]: r for r in out["workflows"][0]["results"]}
    assert rows["ex:sp1"]["verdict"] == "ACHIEVABLE"
    assert "min_max_units" in rows["ex:sp2"]["missing"]


def test_graph_tab_refuses_jsonld():
    with pytest.raises(ValueError, match="JSON-LD"):
        app.twin_explore("graph.jsonld", b"{}")
    with pytest.raises(ValueError, match="JSON-LD"):
        app.twin_graph("graph.jsonld", b"{}")


def test_why_cases_are_decided_live():
    """Tab 3: every case's skillc column comes from the real checker or monitor."""
    got = {c["id"]: app.why_run(c["id"]) for c in app.WHY["cases"]}
    assert got["slack-note"]["verdict"] == "IMPOSSIBLE"
    assert got["slack-note"]["missing"] == ["slack_send_message"]
    assert got["chat-repo"]["missing"] == ["edit", "grep", "read"]
    assert got["deploy"]["plan_decision"] == "deny" and "BLOCKED_GUARD" in got["deploy"]["plan_reason"]
    assert got["email-cfo"]["plan_decision"] == "deny" and "send_email" in got["email-cfo"]["plan_reason"]
    push = got["force-push"]["steps"]
    assert [s["decision"] for s in push] == ["allow", "allow", "deny"]
    approve = got["self-approve"]["steps"]
    assert approve[-1]["tool"] == "write_revenue_analysis" and approve[-1]["decision"] == "deny"
    assert all(r["stopped"] for r in got.values() if r["mode"] == "runtime")


def test_why_cases_say_where_columns_come_from():
    for c in app.WHY["cases"]:
        assert c["provenance"] in ("measured", "illustrative", "mixed")
        assert c["provenance"] == "illustrative" or c.get("source")
        assert c["setup"] in {s["id"] for s in app.WHY["setups"]}
    with pytest.raises(ValueError):
        app.why_run("no-such-case")


def test_graph_tab_draws_entities_and_links():
    pytest.importorskip("rdflib")
    g = app.twin_graph(app.GRAPH_EXAMPLE.name, app.GRAPH_EXAMPLE.read_bytes())
    ids = {n["id"]: n for n in g["nodes"]}
    assert ids["ex:sp11"]["kind"] == "point" and ids["ex:vav11"]["kind"] == "equipment"
    assert ids["ex:zone11"]["kind"] == "place" and ids["ex:hq"]["kind"] == "structure"
    assert {"s": "ex:vav11", "t": "ex:zone11", "p": "feeds"} in g["edges"]
    # classes, units, literals and blank nodes are details, never drawn as entities
    assert "unit:DEG_C" not in ids and all(not i.startswith("_:") for i in ids)
    assert ["minPresentValue", "16.0"] in ids["ex:sp11"]["details"]


def test_graph_tab_runs_the_built_in_verifiers_without_a_workflow():
    pytest.importorskip("rdflib")
    out = app.twin_check(app.GRAPH_EXAMPLE.name, app.GRAPH_EXAMPLE.read_bytes(), "")
    by = {w["title"]: {r["target"]: r for r in w["results"]} for w in out["workflows"]}
    sp = by["Set-point verifier"]
    assert sp["ex:sp11"]["verdict"] == "ACHIEVABLE"
    assert sp["ex:sp12"]["missing"] == ["min_max_units"]
    assert sp["ex:sp13"]["missing"] == ["external_reference"]
    zone = by["Schedule-update verifier"]
    assert zone["ex:zone11"]["verdict"] == "ACHIEVABLE"
    assert "operating_policy" in zone["ex:zone21"]["missing"]
    # each piece of evidence carries the graph path that proves it
    places = next(e for e in sp["ex:sp11"]["evidence"] if e["key"] == "controlled_places")
    assert any("ex:vav11 ->feeds ex:zone11" in line for line in places["found"])
