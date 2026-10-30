"""demo/skillc-here: the environment tab and the graph tab, without the server."""
import importlib.util
import json
from pathlib import Path

import pytest

from skillc.env import copilot

MODULE_PATH = Path(__file__).resolve().parents[1] / "demo" / "skillc-here" / "app.py"
SPEC = importlib.util.spec_from_file_location("skillc_here_app", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


@pytest.fixture
def env(tmp_path):
    # no Copilot settings, approvals, MCP configs or credentials: the built-in tools only
    return app.read_environment(refresh=True, probe=lambda: copilot.probe(
        root=tmp_path, home=tmp_path / "copilot-home", credentials=(), check_egress=False))


def _skill(name):
    return next(s["text"] for s in app.samples() if s["name"] == name)


def _verdicts(result):
    return {r["setting"]: (r["verdict"], r["missing"]) for r in result["rows"]}


def test_environment_lists_copilot_tools_and_grants(env):
    names = {t["name"] for t in env["tools"]}
    assert {"view", "edit", "grep"} <= names
    assert names & {"bash", "powershell"}
    assert {"bash", "view", "edit"} <= set(env["grants"])     # any shell grants `bash`
    assert env["credentials"] == []
    assert env["runtime"] == "GitHub Copilot CLI"
    assert [m["name"] for m in env["mcp"]] == ["github"]


def test_same_skill_differs_by_setting(env):
    v = _verdicts(app.check_skill(_skill("fix-failing-test"), app.settings(env)))
    assert list(v) == ["this machine", "Copilot CLI", "VS Code Copilot", "Claude Code",
                       "claude.ai"]
    assert v["this machine"][0] == "ACHIEVABLE"
    assert v["Copilot CLI"][0] == "ACHIEVABLE"
    assert v["Claude Code"][0] == "ACHIEVABLE"              # `view` is Claude Code's `Read`
    assert v["claude.ai"] == ("IMPOSSIBLE", ["grep"])
    v = _verdicts(app.check_skill(_skill("book-a-table"), app.settings(env)))
    assert v["claude.ai"][0] == "ACHIEVABLE"
    assert v["this machine"][0] == "ACHIEVABLE"             # ask_user + web_search
    assert v["VS Code Copilot"] == ("IMPOSSIBLE", ["web_search"])


def test_cells_say_which_equivalent_tool_was_counted(env):
    r = app.check_skill(_skill("book-a-table"), app.settings(env))
    rows = {x["setting"]: x for x in r["rows"]}
    assert rows["Copilot CLI"]["matched"] == [["ask_user_input_v0", "ask_user"]]
    assert ["web_search", "websearch"] in rows["Claude Code"]["matched"]
    assert rows["claude.ai"]["matched"] == []


def test_what_if_changes_only_this_machine(env):
    where = app.settings(env)
    where["this machine"] = [*env["grants"], "slack_send_message"]
    v = _verdicts(app.check_skill(_skill("post-release-note"), where))
    assert v["Copilot CLI"] == ("IMPOSSIBLE", ["slack_send_message"])
    assert v["this machine"][0] == "ACHIEVABLE"


def test_profiles_with_a_shell_grant_bash():
    assert "bash" in app.profile_grants("vscode-copilot")
    assert "bash" in app.profile_grants("copilot-cli")


# --- tab 1's LLM columns, with the model stubbed ------------------------------------------

def _stub(replies, seen):
    def complete(provider, system, user, model, timeout):
        seen.append((system, json.loads(user)))
        from skillc.frontend import providers
        providers._record_usage({"input_tokens": 100, "output_tokens": 20})
        return replies(json.loads(user))
    return complete


def _all(verdict):
    return lambda req: json.dumps({"settings": {
        r["id"]: {"verdict": verdict, "missing": [], "reason": "r"} for r in req["runtimes"]}})


@pytest.fixture
def llm_on(monkeypatch):
    monkeypatch.setitem(app.LLM, "enabled", True)
    monkeypatch.setitem(app.LLM, "provider", "azure-openai")
    monkeypatch.setitem(app.LLM, "model", "stub")


def test_llm_columns_are_off_without_the_opt_in(env, monkeypatch):
    monkeypatch.delenv("SKILLC_ALLOW_MODEL_CALLS", raising=False)
    monkeypatch.setitem(app.LLM, "enabled", False)
    assert app.enable_llm("azure-openai", None)["enabled"] is False
    with pytest.raises(ValueError, match="off"):
        app.llm_checks(_skill("fix-failing-test"), app.settings(env), env)


def test_both_llms_get_the_same_facts_and_only_guided_gets_the_guide(env, llm_on):
    seen = []
    out = app.llm_checks(_skill("fix-failing-test"), app.settings(env), env,
                         complete=_stub(_all("ACHIEVABLE"), seen))
    names = list(app.settings(env))
    assert len(seen) == 2 * len(names)                       # one call per cell
    plain = [(s, u) for s, u in seen if app.llm_check.GUIDE not in s]
    guided = [(s, u) for s, u in seen if app.llm_check.GUIDE in s]
    assert sorted(json.dumps(u) for _s, u in plain) == sorted(json.dumps(u) for _s, u in guided)
    assert guided[0][0] == plain[0][0] + "\n\n" + app.llm_check.GUIDE
    assert "look at the tools first" in app.llm_check.GUIDE.lower()
    rows = out["arms"]["plain"]["rows"]
    assert [r["setting"] for r in rows] == names
    assert all(r["input_tokens"] == 100 and r["output_tokens"] == 20 for r in rows)
    assert all(isinstance(r["ms"], int) for r in rows)
    assert out["arms"]["guided"]["input_tokens"] == 100 * len(names)


def test_llm_request_uses_neutral_ids_and_no_paths_or_domains(env, llm_on, tmp_path):
    seen = []
    app.llm_checks(_skill("fix-failing-test"), app.settings(env), env,
                   complete=_stub(_all("UNKNOWN"), seen))
    sent = json.dumps([u for _s, u in seen])
    assert all([r["id"] for r in u["runtimes"]] == ["s1"] for _s, u in seen)
    assert "claude.ai" not in sent and str(tmp_path) not in sent
    machine = next(u["runtimes"][0] for _s, u in seen
                   if "tools_that_ask_first" in u["runtimes"][0])
    assert machine["mcp_servers_tools_not_listed"] == ["github"]
    assert "edit" in machine["tools_that_ask_first"]
    assert sum("tools_that_ask_first" in u["runtimes"][0] for _s, u in seen) == 2


def test_a_failed_or_partial_llm_answer_is_unknown(env, llm_on):
    def boom(*a):
        raise RuntimeError("no deployment")
    out = app.llm_checks(_skill("fix-failing-test"), app.settings(env), env, complete=boom)
    assert {r["verdict"] for r in out["arms"]["plain"]["rows"]} == {"UNKNOWN"}
    assert "no deployment" in out["arms"]["plain"]["error"]
    partial = lambda req: json.dumps({"settings": {"s9": {"verdict": "maybe"}}})
    out = app.llm_checks(_skill("fix-failing-test"), app.settings(env), env,
                         complete=_stub(partial, []))
    rows = out["arms"]["guided"]["rows"]
    assert rows[0]["verdict"] == "UNKNOWN" and rows[1]["reason"] == "no answer for this setting"


def test_skillc_cells_report_zero_tokens_and_their_time(env):
    r = app.check_skill(_skill("fix-failing-test"), app.settings(env))
    assert r["compile_ms"] > 0
    assert all(x["tokens"] == 0 and x["ms"] >= 0 for x in r["rows"])


# --- tab 2's other forms: a sketch or description, and a picture -------------------------

def test_sketch_examples_load_check_and_report_their_reading():
    pytest.importorskip("rdflib")
    for path in app.SKETCH_EXAMPLES:
        data = path.read_bytes()
        reading = app.sketch_reading(path.name, data)
        assert reading["read"] and reading["ignored"] == []
        out = app.twin_check(path.name, data, "")
        sp = {r["target"]: r for r in out["workflows"][0]["results"]}
        assert sp["ex:sp-11"]["verdict"] == "ACHIEVABLE"
        assert sp["ex:sp-12"]["missing"] == ["min_max_units"]
    assert app.sketch_reading("graph.ttl", b"") is None


def test_picture_needs_the_opt_in(monkeypatch):
    monkeypatch.setitem(app.LLM, "enabled", False)
    with pytest.raises(ValueError, match="needs a model"):
        app.twin_transcribe("aGVsbG8=", "image/png")


def test_picture_is_transcribed_then_read_without_a_model(llm_on):
    import base64
    seen = {}

    def complete(provider, system, user, model, timeout, json_mode=True, image=None):
        seen.update(system=system, image=image, json_mode=json_mode)
        return "```\nAHU-1 -> VAV-1 -> Zone 1\nSP-1 on VAV-1: 16..26 degC\nsomething vague\n```"

    png = base64.b64encode(b"\x89PNG not really").decode()
    out = app.twin_transcribe(png, "image/png", complete=complete)
    assert seen["image"] == (b"\x89PNG not really", "image/png") and seen["json_mode"] is False
    assert "never add" in seen["system"]
    assert out["text"].splitlines()[0] == "AHU-1 -> VAV-1 -> Zone 1"
    assert [x["text"] for x in out["reading"]["ignored"]] == ["something vague"]
    with pytest.raises(ValueError, match="base64"):
        app.twin_transcribe("not base64!", "image/png", complete=complete)


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
    assert got["chat-repo"]["missing"] == ["grep"]
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


def test_graph_results_explain_each_required_and_optional_input():
    pytest.importorskip("rdflib")
    out = app.twin_check(app.GRAPH_EXAMPLE.name, app.GRAPH_EXAMPLE.read_bytes(), "")
    for workflow in out["workflows"]:
        assert workflow["request"]
        for result in workflow["results"]:
            assert all(e["why"] for e in result["evidence"])
    by = {w["title"]: {r["target"]: r for r in w["results"]} for w in out["workflows"]}
    sp = by["Set-point verifier"]
    limits = next(e for e in sp["ex:sp12"]["evidence"] if e["key"] == "min_max_units")
    assert limits["status"] == "missing"
    assert "applicable equipment limits" in limits["why"]
    assert "no minimum/maximum" in limits["note"]
    history = next(e for e in sp["ex:sp_orphan"]["evidence"] if e["key"] == "history")
    assert history["status"] == "missing" and not history["critical"]
    assert "history" not in sp["ex:sp_orphan"]["missing"]
    policy = next(e for e in by["Schedule-update verifier"]["ex:zone21"]["evidence"]
                  if e["key"] == "operating_policy")
    assert policy["status"] == "missing" and "permitted hours" in policy["why"]


def test_custom_workflow_replaces_the_default_evidence_question():
    pytest.importorskip("rdflib")
    data = app.GRAPH_EXAMPLE.read_bytes()
    default = app.twin_check(app.GRAPH_EXAMPLE.name, data, "")
    workflow = "# Temperature evidence review\nEvidence needed:\n" \
               "- Set-point identity and type\n- Configured minimum/maximum and units\n"
    custom = app.twin_check(app.GRAPH_EXAMPLE.name, data, workflow)
    assert len(custom["workflows"]) == 1
    result = custom["workflows"][0]
    assert result["title"] == "Temperature evidence review"
    original = {r["target"]: r for r in default["workflows"][0]["results"]}
    changed = {r["target"]: r for r in result["results"]}
    # This narrower checklist no longer asks for a BACnet reference.
    assert original["ex:sp13"]["verdict"] == "IMPOSSIBLE"
    assert changed["ex:sp13"]["verdict"] == "ACHIEVABLE"
    assert changed["ex:sp12"]["verdict"] == "IMPOSSIBLE"
    assert changed["ex:sp12"]["missing"] == ["min_max_units"]
    assert all(len(r["evidence"]) == 2 for r in result["results"])


def test_graph_stream_yields_before_checking_all_targets_and_releases_lock(monkeypatch):
    from contextlib import closing
    from skillc.env import twin

    pytest.importorskip("rdflib")
    checked = []
    verify = twin.verify_target

    def track(*args, **kwargs):
        checked.append(args[2])
        return verify(*args, **kwargs)

    monkeypatch.setattr(twin, "verify_target", track)
    with closing(app.twin_check_events(
            app.GRAPH_EXAMPLE.name, app.GRAPH_EXAMPLE.read_bytes(), "")) as events:
        first = next(events)
        assert first["event"] == "workflow" and first["targets"] == 10
        assert checked == []
        result = next(events)
        assert result["event"] == "result" and result["result"]["target"] == "ex:sp11"
        assert len(checked) == 1
    assert app._LOCK.acquire(blocking=False)
    app._LOCK.release()


def test_graph_stream_http_emits_results_and_explicit_errors():
    import threading
    import urllib.request

    pytest.importorskip("rdflib")
    server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        endpoint = f"http://127.0.0.1:{server.server_port}/api/twin/stream"
        body = {"graph": app.GRAPH_SMALL.read_text("utf-8"),
                "filename": app.GRAPH_SMALL.name, "workflow": ""}
        request = urllib.request.Request(
            endpoint, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=15) as response:
            assert response.headers["Content-Type"] == "application/x-ndjson; charset=utf-8"
            events = [json.loads(line) for line in response]
        assert events[0]["event"] == "workflow" and events[-1]["event"] == "complete"
        assert sum(e["event"] == "workflow_complete" for e in events) == 2
        streamed = [e["result"] for e in events if e["event"] == "result"]
        expected = app.twin_check(app.GRAPH_SMALL.name, app.GRAPH_SMALL.read_bytes(), "")
        summary = lambda rows: [(r["target"], r["verdict"], r["missing"]) for r in rows]
        assert summary(streamed) == summary(
            [r for w in expected["workflows"] for r in w["results"]])
        body["workflow"] = "not an evidence checklist"
        request = urllib.request.Request(
            endpoint, json.dumps(body).encode(), {"Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=15) as response:
            error = [json.loads(line) for line in response]
        assert len(error) == 1 and error[0]["event"] == "error"
        assert "no evidence needs" in error[0]["error"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_campus_room_context_follows_graph_links_and_preserves_constraint_values():
    pytest.importorskip("rdflib")
    graph = app.twin_graph(app.GRAPH_EXAMPLE.name, app.GRAPH_EXAMPLE.read_bytes())
    case = graph["case"]
    assert case["counts"] == {
        "buildings": 1, "floors": 3, "zones": 9, "rooms": 18,
        "equipment": 12, "setpoints": 10,
    }
    rooms = {r["id"]: r for r in case["rooms"]}
    assert "ex:sp_orphan" not in rooms
    room = rooms["ex:room111"]
    assert room["description"] == ""  # the fixture has no room-use descriptions
    assert room["containers"] == ["ex:zone11", "ex:floor1", "ex:hq"]
    assert room["setpoints"] == ["ex:sp11"] and room["equipment"] == ["ex:vav11"]
    assert room["schedule_targets"] == ["ex:zone11"]
    assert {"ex:sched11", "ex:policy_office_hours"} <= set(room["context_nodes"])
    assert "ex:sp_orphan" not in room["context_nodes"]
    assert any("ex:vav11 ->feeds ex:zone11 ->hasPart ex:room111" in p for p in room["paths"])
    nodes = {n["id"]: n for n in graph["nodes"]}
    assert any("activePriority=9" in value for _, value in nodes["ex:sp11"]["details"])
    assert any("saturday=08:00-13:00" in value for _, value in nodes["ex:sched11"]["details"])
    assert ["minSetpoint", "18.0"] in nodes["ex:policy_office_hours"]["details"]
    assert "ex:policy_office_hours" not in rooms["ex:room211"]["context_nodes"]
    assert not any(n.startswith("ex:sched") for n in rooms["ex:room311"]["context_nodes"])


def test_room_context_uses_inverse_links_not_campus_names():
    pytest.importorskip("rdflib")
    graph = b"""
        @prefix ex: <urn:test:> .
        ex:office a ex:Room; ex:isPartOf ex:area; ex:description "An equipment test room." .
        ex:area a ex:Zone; ex:isFedBy ex:terminal .
        ex:terminal a ex:VAV .
        ex:control a ex:Temperature_Setpoint; ex:isPointOf ex:terminal .
    """
    room = app.twin_graph("custom.ttl", graph)["case"]["rooms"][0]
    assert room["description"] == "An equipment test room."
    assert room["setpoints"] == ["ex:control"]
    assert room["schedule_targets"] == ["ex:area"]
    assert room["equipment"] == ["ex:terminal"]
    empty = app.twin_graph("empty-rooms.ttl", b"@prefix ex: <urn:test:> . ex:p a ex:Setpoint .")
    assert empty["case"]["rooms"] == []


def test_measured_benchmark_reports_absence_and_corruption(tmp_path):
    assert not app.measured_benchmark(tmp_path)["available"]
    run = tmp_path / "20261022_here_benchmark"
    run.mkdir()
    (run / "results.json").write_text("not JSON", encoding="utf-8")
    result = app.measured_benchmark(tmp_path)
    assert not result["available"] and "Cannot read benchmark" in result["reason"]


def test_measured_benchmark_exposes_aggregates_not_raw_settings(tmp_path):
    import json
    run = tmp_path / "20261022_here_benchmark"
    run.mkdir()
    data = {"schema": "skillc.here-benchmark/1", "cases": [
        {"id": "local", "source": "repository"}], "repeats": 1, "live": True,
        "model": "stub", "rows": [{}, {}, {}], "summary": {"skillc": {"trials": 1}},
        "oracle": {"local": {"feasible": True, "goal_status": {"report_ready": True}}},
        "discovery_ms": 1,
        "environment": {"do_not_expose": True}, "transcript": "do not expose"}
    (run / "results.json").write_text(json.dumps(data), encoding="utf-8")
    out = app.measured_benchmark(tmp_path)
    assert out["available"] and out["completed"]
    assert out["cases"][0]["feasible"] is True
    assert out["cases"][0]["task"] == "local"
    assert out["cases"][0]["deliverables"] == {"report_ready": True}
    assert "environment" not in out and "transcript" not in out and "rows" not in out
    data["rows"] = [{}]
    (run / "results.json").write_text(json.dumps(data), encoding="utf-8")
    assert not app.measured_benchmark(tmp_path)["completed"]


def test_benchmark_http_endpoint_and_demo_page(monkeypatch):
    import json
    import threading
    import urllib.request

    monkeypatch.setattr(app, "measured_benchmark",
                        lambda: {"available": False, "reason": "No local benchmark yet."})
    server = app.ThreadingHTTPServer(("127.0.0.1", 0), app.Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        base = f"http://127.0.0.1:{server.server_port}"
        with urllib.request.urlopen(base + "/api/benchmark", timeout=5) as response:
            result = json.load(response)
        assert result == {"available": False, "reason": "No local benchmark yet."}
        with urllib.request.urlopen(base, timeout=5) as response:
            page = response.read().decode("utf-8")
        assert 'id="benchOut"' in page and 'api("/api/benchmark")' in page
        assert 'id="benchReference"' in page
        assert page.index('id="benchReference"') < page.index('id="whySetup"')
        assert "published comparison above is still available" in page
        with urllib.request.urlopen(base + "/benchmark-report", timeout=5) as response:
            report = response.read().decode("utf-8")
            assert response.headers["Content-Type"] == "text/plain; charset=utf-8"
        assert "33,047" in report and "44,724" in report
        assert "not universal superiority" in report
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
