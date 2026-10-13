"""The in-sandbox self-probe, the hosted merge rules, the watcher factory, telemetry."""
from __future__ import annotations

import argparse
import http.server
import json
import socket
import sys
import textwrap
import threading

import pytest

from skillc import telemetry
from skillc.env import mcp, selfprobe, watch
from skillc.env.facts import need
from skillc.env.model import Environment, validate_env
from skillc.env.selfprobe import (add_self_opts, hosted_probe_factory, merge_hosted, probe,
                                  self_probe_from_args)

ABSENT = "skillc-no-such-program"
SECRET = "sekret-value-0xdeadbeef"
TOOLBOX = "https://acct.services.ai.azure.com/api/projects/p/toolboxes/tb/versions/1/mcp?api-version=v1"


def dump(env: Environment) -> str:
    return json.dumps(env.to_dict())


# --------------------------------------------------------------------------
# The probe on this machine
# --------------------------------------------------------------------------

@pytest.fixture
def local(monkeypatch):
    monkeypatch.setenv("SKILLC_SELFPROBE_KEY", SECRET)
    monkeypatch.setenv("FOUNDRY_AGENT_SESSION_ID", "sess-42")
    monkeypatch.setenv("AGENT_NAME", "finance-agent")
    monkeypatch.setenv("FOUNDRY_SOMETHING_SECRET", "another-" + SECRET)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://acct.services.ai.azure.com/api/projects/p")
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    return probe(hosts=(), programs=["python", ABSENT], modules=["json", "skillc_nope"])


def test_probe_is_a_valid_environment_with_the_sandbox_facts(local):
    validate_env(local.to_dict())
    assert local.sources == [{"adapter": "self", "mode": "live",
                              "detail": "finance-agent@unknown session sess-42"}]
    kinds = {n["kind"] for n in local.nodes.values()}
    assert kinds >= {"principal", "scope", "service"}
    assert all(n["attrs"].get("observed") for n in local.nodes.values())
    platform = sys.platform
    expected = {"win32": "windows", "darwin": "macos"}.get(platform, "linux")
    assert need(local, {"platform": expected}).value is True
    sandbox = local.nodes["sandbox"]["attrs"]
    assert sandbox["cpu_count"] >= 1 and sandbox["type"] == "sandbox"
    assert "memory_gib" in sandbox or local.is_unknown("sandbox:memory_gib")
    assert sandbox["free_disk_gib"] > 0


def test_paths_default_to_home_and_files(local):
    home = selfprobe._home()
    node = local.nodes[f"path:{home}".lower()]
    assert node["attrs"]["exists"] and node["attrs"]["writable"] and node["attrs"]["alias"] == "$HOME"
    assert need(local, {"path": f"{home}/x/y.txt"}).value is True   # facts.py joins with "/"
    files = [n for n in local.of_kind("scope") if n["attrs"].get("alias") == "/files"]
    assert len(files) == 1


def test_programs_and_modules(local):
    assert need(local, {"program": "python"}).value is True
    assert need(local, {"program": ABSENT}).value is False
    assert need(local, {"pymodule": "json"}).value is True
    assert need(local, {"pymodule": "skillc_nope"}).value is False
    assert need(local, {"program": "never-asked"}).value is None


def test_credentials_are_names_only(local):
    assert need(local, {"credential": "SKILLC_SELFPROBE_KEY"}).value is True
    assert need(local, {"credential": "FOUNDRY_SOMETHING_SECRET"}).value is True
    assert need(local, {"credential": "ANTHROPIC_API_KEY"}).value in (True, False)
    assert SECRET not in dump(local)
    principal = local.principal()
    assert principal["id"] == "principal/agent/finance-agent"
    assert principal["attrs"]["identity_mode"] == "agent"
    assert {"AGENT_NAME", "FOUNDRY_AGENT_SESSION_ID", "FOUNDRY_SOMETHING_SECRET"} <= set(
        principal["attrs"]["env_vars"])
    assert principal["attrs"]["project_host"] == "https://acct.services.ai.azure.com"
    assert local.nodes["app_insights"]["attrs"]["available"] is False


def test_app_insights_presence_is_recorded_without_the_value(monkeypatch):
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=" + SECRET)
    env = probe(hosts=(), paths=())
    assert env.nodes["app_insights"]["attrs"]["available"] is True
    assert need(env, {"credential": "APPLICATIONINSIGHTS_CONNECTION_STRING"}).value is True
    assert SECRET not in dump(env)


# --------------------------------------------------------------------------
# Egress: the private-address refusal and --inside-network
# --------------------------------------------------------------------------

class _Counting(http.server.HTTPServer):
    requests = 0

    def process_request(self, request, client_address):
        self.requests += 1
        super().process_request(request, client_address)


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *a):
        pass


@pytest.fixture
def local_server():
    server = _Counting(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server
    server.shutdown()
    server.server_close()


def test_inside_network_lifts_the_private_address_refusal(local_server, monkeypatch):
    port = local_server.server_address[1]
    real = socket.getaddrinfo

    def private(host, p, *a, **k):
        if host == "svc.internal":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]
        return real(host, p, *a, **k)

    monkeypatch.setattr(socket, "getaddrinfo", private)
    host = f"http://svc.internal:{port}/"
    ok, why = selfprobe.egress(host, 5.0, inside_network=False)
    assert ok is False and "non-public address 127.0.0.1" in why
    assert local_server.requests == 0
    ok, why = selfprobe.egress(host, 5.0, inside_network=True)
    assert (ok, why) == (True, "HTTP 200")
    assert local_server.requests == 1
    env = probe(hosts=[host], paths=(), inside_network=True)
    node = env.nodes[f"egress/{host}".lower().rstrip("/")]
    assert node["attrs"]["available"] is True and node["attrs"]["inside_network"] is True
    assert local_server.requests == 2


def test_the_probe_refuses_without_contact_by_default(local_server, monkeypatch):
    port = local_server.server_address[1]
    env = probe(hosts=[f"http://127.0.0.1:{port}/"], paths=())
    fact = need(env, {"egress": f"http://127.0.0.1:{port}/"})
    assert fact.value is False and "refused" in fact.reasons[0]
    assert local_server.requests == 0


# --------------------------------------------------------------------------
# The toolbox from the inside
# --------------------------------------------------------------------------

def test_toolbox_is_unknown_until_http_listing_exists(monkeypatch):
    monkeypatch.delattr(mcp, "list_http_tools", raising=False)
    env = probe(hosts=(), paths=(), toolbox_url=TOOLBOX, token_provider=lambda: "tok-" + SECRET)
    assert env.nodes["toolbox/tb"]["attrs"]["url"].endswith("/versions/1/mcp")
    assert "api-version" not in env.nodes["toolbox/tb"]["attrs"]["url"]
    assert {"what": "mcp_tools:toolbox/tb", "why": "HTTP MCP listing unavailable"} in env.unknown
    assert need(env, {"mcp_tool": "search"}).value is None
    assert SECRET not in dump(env)


def test_toolbox_tools_are_observed_with_the_token(monkeypatch):
    seen = {}

    def fake(url, token, timeout):
        seen.update(url=url, token=token, timeout=timeout)
        return [{"name": "azure_ai_search", "description": "search"}, {"name": "a2a"}]

    monkeypatch.setattr(mcp, "list_http_tools", fake, raising=False)
    env = probe(hosts=(), paths=(), toolbox_url=TOOLBOX, token_provider=lambda: "tok-" + SECRET)
    assert seen["url"] == TOOLBOX and seen["token"] == "tok-" + SECRET
    assert need(env, {"mcp_tool": "azure_ai_search"}).value is True
    assert env.nodes["toolbox/tb/a2a"]["attrs"]["observed"] is True
    assert not any(u["what"].startswith("mcp_tools:") for u in env.unknown)
    assert SECRET not in dump(env)


def test_toolbox_without_a_token_source_is_unknown(monkeypatch):
    monkeypatch.setattr(mcp, "list_http_tools", lambda *a: [{"name": "x"}], raising=False)
    monkeypatch.setitem(sys.modules, "azure.identity", None)
    monkeypatch.setitem(sys.modules, "azure", None)
    env = probe(hosts=(), paths=(), toolbox_url=TOOLBOX)
    why = next(u["why"] for u in env.unknown if u["what"] == "mcp_tools:toolbox/tb")
    assert "azure-identity" in why
    monkeypatch.setattr(mcp, "list_http_tools", lambda *a: 1 / 0, raising=False)
    env = probe(hosts=(), paths=(), toolbox_url=TOOLBOX, token_provider=lambda: "t")
    why = next(u["why"] for u in env.unknown if u["what"] == "mcp_tools:toolbox/tb")
    assert why.startswith("tools/list failed")


# --------------------------------------------------------------------------
# Merge rules
# --------------------------------------------------------------------------

def control_plane() -> Environment:
    env = Environment(captured_at="2026-10-01T00:00:00Z")
    env.sources.append({"adapter": "azd", "mode": "declared", "detail": "azure.yaml"})
    env.add_node("/", "scope", "finance", level="root", declared=True)
    p = env.add_node("principal/agent/finance-agent", "principal", "finance-agent", type="agent",
                     identity_mode="agent", declared=True, cpu="1.0", memory="2Gi")
    env.add_node("egress/api.example.com", "service", "api.example.com", type="egress",
                 declared=True, available=False)
    env.add_node("program/jq", "service", "jq", type="program", declared=True, available=True)
    env.add_node("connection/search", "service", "search", type="connection", declared=True,
                 available=True, auth_type="AAD")
    env.add_edge(p, env.add_node("role/reader", "role", "Reader", actions=["*/read"]),
                 "assigned", scope="/")
    tb = env.add_node("toolbox/tb", "mcp_server", "tb", transport="toolbox", declared=True)
    env.add_edge(tb, env.add_node("toolbox/tb/mcp", "tool", "mcp", declared=True), "exposes")
    env.mark_unknown("mcp_tools:toolbox/tb", "tools of a connected MCP server are not declared")
    env.mark_unknown("egress", "measure from inside the sandbox")
    env.mark_unknown("role_assignments", "not read")
    return env


def data_plane() -> Environment:
    env = Environment(captured_at="2026-10-02T00:00:00Z")
    env.sources.append({"adapter": "self", "mode": "live", "detail": "finance-agent@3 session s"})
    env.add_node("/", "scope", "session", level="root", observed=True)
    env.add_node("principal/agent/finance-agent", "principal", "finance-agent", type="agent",
                 identity_mode="obo-looking-wrong", observed=True, session="s")
    env.add_node("egress/api.example.com", "service", "api.example.com", type="egress",
                 observed=True, available=True, why="HTTP 200")
    env.add_node("program/jq", "service", "jq", type="program", observed=True, available=False)
    env.add_node("pymodule/pandas", "service", "pandas", type="python module", observed=True,
                 available=True)
    env.add_node("connection/search", "service", "search", type="connection", observed=True,
                 available=False)
    tb = env.add_node("toolbox/tb", "mcp_server", "tb", transport="toolbox", observed=True)
    env.add_edge(tb, env.add_node("toolbox/tb/search", "tool", "search", observed=True),
                 "exposes")
    env.mark_unknown("sandbox:memory_gib", "no /proc/meminfo")
    return env


def test_merge_precedence_and_conflicts():
    merged = merge_hosted(control_plane(), data_plane())
    validate_env(merged.to_dict())
    # data plane wins for egress and programs, and the disagreement is recorded
    assert need(merged, {"egress": "api.example.com"}).value is True
    assert need(merged, {"program": "jq"}).value is False
    assert {"what": "conflict:egress/api.example.com",
            "why": "declared False, observed True; observed used"} in merged.unknown
    assert {"what": "conflict:program/jq",
            "why": "declared True, observed False; observed used"} in merged.unknown
    # control plane wins for connections and principal attributes
    assert merged.nodes["connection/search"]["attrs"]["available"] is True
    assert {"what": "conflict:connection/search",
            "why": "declared True, observed False; declared used"} in merged.unknown
    principal = merged.principal()["attrs"]
    assert principal["identity_mode"] == "agent" and principal["cpu"] == "1.0"
    assert principal["session"] == "s"                 # data-only attrs are added
    # union: roles from control, modules from data, both toolbox tools
    assert need(merged, {"pymodule": "pandas"}).value is True
    assert merged.out_edges("principal/agent/finance-agent", "assigned")
    assert need(merged, {"mcp_tool": "search"}).value is True
    assert "toolbox/tb/mcp" in merged.nodes
    # answered unknowns are dropped, the rest kept, sources concatenated
    whats = {u["what"] for u in merged.unknown}
    assert "egress" not in whats and "mcp_tools:toolbox/tb" not in whats
    assert {"role_assignments", "sandbox:memory_gib"} <= whats
    assert [s["adapter"] for s in merged.sources] == ["azd", "self"]
    assert merged.captured_at == "2026-10-02T00:00:00Z"


def test_merge_without_overlap_is_a_plain_union():
    control, data = control_plane(), Environment()
    data.add_node("sandbox", "service", "sandbox", type="sandbox", observed=True, cpu_count=2)
    merged = merge_hosted(control, data)
    assert set(merged.nodes) == set(control.nodes) | {"sandbox"}
    assert not any(u["what"].startswith("conflict:") for u in merged.unknown)
    assert merged.is_unknown("egress")


# --------------------------------------------------------------------------
# Command-line wiring and the watcher
# --------------------------------------------------------------------------

def test_add_self_opts_shares_existing_options():
    sp = argparse.ArgumentParser()
    sp.add_argument("--host", action="append", help="existing")
    add_self_opts(sp)
    add_self_opts(sp)                                   # idempotent
    args = sp.parse_args(["--self", "--host", "a", "--host", "b", "--inside-network",
                          "--needs-from", "x", "--toolbox-url", TOOLBOX, "--program", "jq"])
    assert args.self and args.host == ["a", "b"] and args.inside_network
    assert args.needs_from == ["x"] and args.toolbox_url == TOOLBOX and args.program == ["jq"]


def test_needs_from_a_skills_directory(tmp_path, monkeypatch):
    asked = []
    monkeypatch.setattr(selfprobe, "egress", lambda h, t, inside_network=False:
                        (asked.append(h), (True, "HTTP 200"))[1])
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "Fetcher.md").write_text(textwrap.dedent("""\
        ---
        name: fetcher
        description: Fetch a dataset.
        ---
        ```bash
        pip install pandas
        curl -s https://api.example.com/data.csv | jq .
        ```

        ```python
        import pandas as pd
        ```
        """), encoding="utf-8")
    args = argparse.Namespace(needs_from=[str(tmp_path / "skills")], host=["extra.example.org"],
                              program=None, module=None, path=None, inside_network=False,
                              toolbox_url=None)
    env = self_probe_from_args(args)
    assert {"api.example.com", "extra.example.org", "pypi.org"} <= set(asked)
    assert "pymodule/pandas" in env.nodes and "program/jq" in env.nodes
    assert need(env, {"egress": "api.example.com"}).value is True
    assert need(env, {"path": f"{selfprobe._home()}/f"}).value is True


def test_hosted_probe_factory_round_trips_through_watch_once(tmp_path):
    args = argparse.Namespace(host=[], program=["python"], module=["json"], path=[],
                              inside_network=False, toolbox_url=None, needs_from=[])
    factory = hosted_probe_factory(args)
    first = watch.watch_once(tmp_path, factory, {})
    assert first["environment_changes"] is None
    latest = Environment.load(tmp_path / watch.LATEST)
    assert latest.sources[0]["adapter"] == "self"
    assert need(latest, {"program": "python"}).value is True
    second = watch.watch_once(tmp_path, factory, {})
    assert second["environment_changes"] == {"added": [], "removed": [], "changed": []}
    assert len(list(tmp_path.glob("env-*.json"))) >= 1


# --------------------------------------------------------------------------
# Telemetry
# --------------------------------------------------------------------------

def test_telemetry_is_a_no_op_without_opentelemetry(monkeypatch):
    monkeypatch.setitem(sys.modules, "opentelemetry", None)
    ran = []
    with telemetry.span("skillc.gate", intent="x", n=1, nested={"a": 1}) as s:
        ran.append(s)
    assert ran == [None]
    telemetry.event("skillc.decision", tool="t", decision="deny")
    with pytest.raises(ZeroDivisionError), telemetry.span("boom"):
        raise ZeroDivisionError("propagates")


def test_telemetry_never_raises_on_a_broken_tracer(monkeypatch):
    class Broken:
        def start_as_current_span(self, *a, **k):
            raise RuntimeError("exporter down")

    monkeypatch.setattr(telemetry, "_tracer", lambda: Broken())
    with telemetry.span("x", a=1) as s:
        assert s is None
    telemetry.event("y")


def test_telemetry_uses_a_tracer_when_present(monkeypatch):
    calls = []

    class Span:
        def __enter__(self):
            calls.append("enter")
            return self

        def __exit__(self, *exc):
            calls.append(("exit", exc[0]))

    class Tracer:
        def start_as_current_span(self, name, attributes=None):
            calls.append((name, attributes))
            return Span()

    monkeypatch.setattr(telemetry, "_tracer", lambda: Tracer())
    with telemetry.span("skillc.verdict", verdict="possible", count=2, obj=object()) as s:
        assert isinstance(s, Span)
    assert calls[0][0] == "skillc.verdict"
    assert calls[0][1]["verdict"] == "possible" and calls[0][1]["count"] == 2
    assert isinstance(calls[0][1]["obj"], str)
    assert calls[1:] == ["enter", ("exit", None)]
    with pytest.raises(ValueError), telemetry.span("err"):
        raise ValueError("x")
    assert calls[-1] == ("exit", ValueError)
