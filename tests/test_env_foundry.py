"""The Foundry adapter: a replayed export of a deployed hosted agent, the HTTP
MCP client against a fake server, sanitised exports, and the CLI options."""
from __future__ import annotations

import argparse
import json
import re
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from skillc.env import azure, foundry, mcp
from skillc.env.azd import from_azure_yaml
from skillc.env.model import Environment, diff, validate_env

ROOT = Path(__file__).parent.parent
FIXTURE = Path(__file__).parent / "fixtures" / "foundry" / "firstProject-finance-report-agent"
DECLARED = ROOT / "examples" / "hosted-agent-finance" / "azure.yaml"
AGENT = "principal/agent/finance-report-agent"
GUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


@pytest.fixture(scope="module")
def observed() -> Environment:
    return foundry.replay(FIXTURE)


@pytest.fixture(scope="module")
def declared() -> Environment:
    return from_azure_yaml(DECLARED)


def node(env: Environment, node_id: str) -> dict:
    assert node_id in env.nodes, sorted(env.nodes)
    return env.nodes[node_id]


# --------------------------------------------------------------------------
# Replay of the recorded export (firstProject, finance-report-agent)
# --------------------------------------------------------------------------

def test_replay_is_a_valid_observed_environment(observed):
    doc = observed.to_dict()
    validate_env(doc)
    again = Environment.from_dict(doc)
    assert again.to_dict()["nodes"] == doc["nodes"]
    assert observed.sources == [{"adapter": "foundry", "mode": "replay",
                                 "detail": "https://foundary-tzuc06.services.ai.azure.com/api/"
                                           "projects/firstProject agent finance-report-agent"}]
    assert observed.captured_at == "2026-10-08T12:11:06Z"           # from the manifest
    assert all(n["attrs"].get("observed") is True for n in observed.nodes.values())
    assert node(observed, "/")["name"] == "firstProject"


def test_replay_is_deterministic_and_offline():
    a, b = foundry.replay(FIXTURE).to_dict(), foundry.replay(FIXTURE).to_dict()
    assert a == b


def test_agent_principal_carries_identity_version_sandbox_and_env_names_only(observed):
    agent = node(observed, AGENT)
    a = agent["attrs"]
    assert agent["kind"] == "principal" and observed.principal()["id"] == AGENT
    assert a["type"] == "agent" and a["identity_mode"] == "agent"
    assert GUID.match(a["object_id"]) and a["object_id"] == a["client_id"]
    assert a["agent_kind"] == "hosted" and a["version"] == "8" and a["status"] == "active"
    assert a["state"] == "enabled"
    assert a["cpu"] == "1.0" and a["memory"] == "2Gi"
    assert a["protocols"] == ["responses 2.0.0"]
    assert a["env_vars"] == ["COORDINATOR_INSTRUCTIONS", "MICROSOFT_FOUNDRY_MODEL_DEPLOYMENT_NAME",
                             "SKILLC_MONITOR", "TOOLBOX_NAME"]
    assert a["runtime"] == "python_3_13" and a["entry_point"] == "python main.py"
    assert a["dependency_resolution"] == "remote_build"
    assert a["endpoint_protocols"] == ["responses"] and a["protocol_configuration"] == ["responses"]
    assert a["a2a"] is False and a["authorization"] == ["Entra"]
    assert a["agent_card"] is True
    assert a["agent_card_skills"] == ["fetcher", "revenue-analyst", "expense-analyst", "writer",
                                      "tax-verifier", "tax-specialist"]
    text = json.dumps(observed.to_dict())
    assert "gpt-5.4" not in text and '"minimal"' not in text         # env var values never


def test_toolbox_has_declared_tools_and_the_observed_mcp_tool_list(observed):
    box = node(observed, "toolbox/finance-tools")
    assert box["kind"] == "mcp_server" and box["attrs"]["transport"] == "toolbox"
    assert box["attrs"]["version"] == "1"
    assert box["attrs"]["url"] == ("https://foundary-tzuc06.services.ai.azure.com/api/projects/"
                                   "firstProject/toolboxes/finance-tools/versions/1/mcp")
    exposed = {e["dst"] for e in observed.out_edges(box["id"], "exposes")}
    assert exposed == {"toolbox/finance-tools/code_interpreter", "toolbox/finance-tools/web_search",
                       "toolbox/finance-tools/mcp/code_interpreter",
                       "toolbox/finance-tools/mcp/web_search"}
    declared = node(observed, "toolbox/finance-tools/code_interpreter")
    assert declared["attrs"]["type"] == "code_interpreter"
    assert declared["attrs"]["require_approval"] == "never"
    listed = node(observed, "toolbox/finance-tools/mcp/code_interpreter")
    assert listed["name"] == "code_interpreter" and listed["attrs"]["observed"] is True
    assert listed["attrs"]["listed_as"] == "agent"
    assert "Python" in listed["attrs"]["description"]
    assert len(listed["attrs"]["description"]) <= 200
    assert node(observed, "toolbox/finance-tools/mcp/web_search")["attrs"]["description"]
    assert not observed.is_unknown("mcp_tools:toolbox/finance-tools")
    assert observed.is_unknown("mcp_tools_identity:toolbox/finance-tools")


def test_connections_carry_category_auth_type_and_host_only(observed):
    names = {n["name"] for n in observed.of_kind("service")}
    assert names == {"openai-tzuc06", "appInsights-connection-0569", "acre39f82e9-conn"}
    openai = node(observed, "connection/openai-tzuc06")
    assert openai["attrs"]["category"] == "AzureOpenAI"
    assert openai["attrs"]["auth_type"] == "ApiKey"
    assert openai["attrs"]["target"] == "https://openai-tzuc06.openai.azure.com"
    assert openai["attrs"]["is_default"] is True and openai["attrs"]["location"] == "swedencentral"
    acr = node(observed, "connection/acre39f82e9-conn")
    assert acr["attrs"]["auth_type"] == "RegistryIdentity"
    assert acr["attrs"]["target"] == "acre39f82e9.azurecr.io"
    text = json.dumps(observed.to_dict())
    assert "Bearer" not in text and "credentials" not in text and "@" not in text.replace("@latest", "")


def test_agent_identity_role_assignments_were_read_and_are_empty(observed):
    assert not observed.is_unknown("role_assignments")
    assert observed.out_edges(AGENT, "assigned") == []
    assert observed.of_kind("role") == []
    assert observed.is_unknown("deny_assignments") and observed.is_unknown("egress")


# --------------------------------------------------------------------------
# Declared (azd) against observed (foundry): the same ids, the diff
# --------------------------------------------------------------------------

def test_node_ids_match_the_azd_conventions(observed, declared):
    for shared in ("toolbox/finance-tools/code_interpreter", "toolbox/finance-tools/web_search",
                   "toolbox/finance-tools", AGENT, "/"):
        assert shared in declared.nodes and shared in observed.nodes
    assert declared.nodes[AGENT]["attrs"]["declared"] is True
    assert observed.nodes[AGENT]["attrs"]["observed"] is True
    for key in ("cpu", "memory", "protocols", "env_vars", "runtime"):
        assert declared.nodes[AGENT]["attrs"][key] == observed.nodes[AGENT]["attrs"][key], key


def test_diff_lists_the_observed_mcp_tools_as_added(observed, declared):
    d = diff(declared, observed)
    assert "tool code_interpreter" in d["added"] and "tool web_search" in d["added"]
    assert "finance-tools -exposes-> code_interpreter" in d["added"]
    assert set(observed.nodes) - set(declared.nodes) >= {
        "toolbox/finance-tools/mcp/code_interpreter", "toolbox/finance-tools/mcp/web_search"}
    assert "unknown mcp_tools_identity:toolbox/finance-tools" in d["added"]
    assert any(line.startswith("principal finance-report-agent:") for line in d["changed"])
    assert "unknown value:FOUNDRY_MODEL_NAME" in d["removed"]            # resolved by the deploy


# --------------------------------------------------------------------------
# A fake Foundry project: HTTP MCP client, live runner, sanitised export
# --------------------------------------------------------------------------

TOKEN = "test-token-0123456789"
OID = "bbbbbbbb-0000-0000-0000-000000000002"
PROJECT_SCOPE = ("/subscriptions/s/resourceGroups/rg/providers/Microsoft.CognitiveServices/"
                 "accounts/acct/projects/proj")
AGENT_DOC = {"name": "x", "state": "enabled",
             "versions": {"latest": {"version": "2"}},
             "agent_endpoint": {"protocols": ["responses", "a2a"],
                                "protocol_configuration": {"responses": {}, "a2a": {}},
                                "authorization_schemes": [{"type": "Entra"}]},
             "instance_identity": {"principal_id": OID, "client_id": OID},
             "agent_card": {"skills": [{"id": "s1"}]}}
VERSION_DOC = {"version": "2", "status": "active", "description": "a test agent",
               "definition": {"kind": "hosted", "cpu": "0.5", "memory": "1Gi",
                              "environment_variables": {"OPENAI_API_KEY": "s3cr3t-value",
                                                        "MODEL": "gpt-test"},
                              "protocol_versions": [{"protocol": "responses",
                                                     "version": "2.0.0"}],
                              "image": "https://acr.azurecr.io/agents/x:2"},
               "instance_identity": {"principal_id": OID, "client_id": OID}}
TOOLBOX_DOC = {"version": "1", "description": "test tools",
               "tools": [{"type": "code_interpreter", "name": "code_interpreter"},
                         {"type": "azure_ai_search", "connection": "search-conn"},
                         {"type": "mcp", "server_label": "docs",
                          "server_url": "https://learn.microsoft.com/api/mcp?key=ZZZ",
                          "allowed_tools": ["microsoft_docs_search"]}]}
CONNECTIONS_DOC = {"value": [{"name": "search-conn", "type": "CognitiveSearch",
                              "target": "https://s.search.windows.net/?api-key=QQQ",
                              "credentials": {"type": "ApiKey", "key": "SECRETVALUE"},
                              "metadata": {"Owner": "alice@contoso.com", "Location": "eu"}}]}
TOOLS = [{"name": "code_interpreter", "description": "run python"},
         {"name": "azure_ai_search", "description": "search the index"},
         {"name": "microsoft_docs_search", "description": "search docs"}]


class FakeFoundry(BaseHTTPRequestHandler):
    """A project data plane: a few GET answers and a streamable HTTP MCP endpoint
    that pages tools/list, assigns a session id and may answer as SSE."""
    sse = False
    seen: list[dict] = []

    def log_message(self, *a):            # quiet
        pass

    def _send(self, status, body=None, content_type="application/json", headers=()):
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        data = b"" if body is None else body.encode("utf-8")
        if data:
            self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self._send(401, '{"error": "unauthorized"}')
        path = urlsplit(self.path).path
        answers = {"/api/projects/proj/agents/x": AGENT_DOC,
                   "/api/projects/proj/agents/x/versions/2": VERSION_DOC,
                   "/api/projects/proj/toolboxes": {"data": [{"name": "tools",
                                                              "default_version": "1"}]},
                   "/api/projects/proj/toolboxes/tools/versions/1": TOOLBOX_DOC,
                   "/api/projects/proj/connections": CONNECTIONS_DOC}
        if path not in answers:
            return self._send(404, '{"error": "no such thing"}')
        return self._send(200, json.dumps(answers[path]))

    def do_POST(self):
        if self.headers.get("Authorization") != f"Bearer {TOKEN}":
            return self._send(401, '{"error": "unauthorized"}')
        msg = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeFoundry.seen.append({"method": msg.get("method"),
                                 "session": self.headers.get("Mcp-Session-Id"),
                                 "accept": self.headers.get("Accept")})
        if "id" not in msg:
            return self._send(202)
        if msg["method"] == "initialize":
            result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}},
                      "serverInfo": {"name": "fake", "version": "0"}}
            headers = [("Mcp-Session-Id", "sess-1")]
        elif msg["method"] == "tools/list":
            if self.headers.get("Mcp-Session-Id") != "sess-1":
                return self._send(400, '{"error": "no session"}')
            cursor = (msg.get("params") or {}).get("cursor")
            result = ({"tools": TOOLS[2:]} if cursor == "page2"
                      else {"tools": TOOLS[:2], "nextCursor": "page2"})
            headers = []
        else:
            return self._send(200, json.dumps({"jsonrpc": "2.0", "id": msg["id"],
                                               "error": {"code": -32601,
                                                         "message": "no such method"}}))
        answer = {"jsonrpc": "2.0", "id": msg["id"], "result": result}
        if FakeFoundry.sse:
            text = json.dumps(answer, indent=1)             # several data: lines per event
            body = "event: message\n" + "".join(f"data: {line}\n" for line in text.splitlines())
            return self._send(200, body + "\n", "text/event-stream", headers)
        return self._send(200, json.dumps(answer), headers=headers)


@pytest.fixture(scope="module")
def server():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeFoundry)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


MCP_PATH = "/api/projects/proj/toolboxes/tools/versions/1/mcp?api-version=v1"


def test_list_http_tools_initialises_pages_and_keeps_the_session(server):
    FakeFoundry.sse, FakeFoundry.seen = False, []
    tools = mcp.list_http_tools(server + MCP_PATH, TOKEN, timeout=5)
    assert [t["name"] for t in tools] == ["code_interpreter", "azure_ai_search",
                                          "microsoft_docs_search"]
    methods = [s["method"] for s in FakeFoundry.seen]
    assert methods == ["initialize", "notifications/initialized", "tools/list", "tools/list"]
    assert [s["session"] for s in FakeFoundry.seen] == [None, "sess-1", "sess-1", "sess-1"]
    assert all("text/event-stream" in s["accept"] for s in FakeFoundry.seen)


def test_list_http_tools_reads_sse_answers(server):
    FakeFoundry.sse = True
    try:
        tools = mcp.list_http_tools(server + MCP_PATH, TOKEN, timeout=5)
    finally:
        FakeFoundry.sse = False
    assert [t["name"] for t in tools] == ["code_interpreter", "azure_ai_search",
                                          "microsoft_docs_search"]


def test_list_http_tools_errors_never_carry_the_token(server):
    with pytest.raises(mcp.MCPProbeError) as e:
        mcp.list_http_tools(server + MCP_PATH, "wrong", timeout=5)
    assert "401" in str(e.value) and "wrong" not in str(e.value) and "api-version" not in str(e.value)
    with pytest.raises(mcp.MCPProbeError):
        mcp.list_http_tools("http://127.0.0.1:9/nothing", TOKEN, timeout=2)


def test_rpc_messages_parses_json_arrays_and_multi_line_sse():
    assert mcp._rpc_messages('[{"id": 1}, {"id": 2}]', "application/json") == [{"id": 1},
                                                                               {"id": 2}]
    sse = ": keep-alive\n\nevent: message\ndata: {\"id\": 1,\ndata:  \"result\": {}}\n\n"
    assert mcp._rpc_messages(sse, "text/event-stream") == [{"id": 1, "result": {}}]
    assert mcp._rpc_messages("", "application/json") == []
    with pytest.raises(mcp.MCPProbeError):
        mcp._rpc_messages("<html>", "text/html")


def fake_az(args):
    """The Azure CLI, for the agent identity's role assignments."""
    azure._assert_read_only(args)
    if args[:3] == ["role", "assignment", "list"]:
        assert args[-2:] == ["--assignee-object-id", OID]
        return [{"roleDefinitionId": f"/subscriptions/s/providers/Microsoft.Authorization/"
                                     f"roleDefinitions/{foundry.AGENT_CONSUMER_ROLE}",
                 "scope": PROJECT_SCOPE, "principalId": OID}]
    raise azure.ProbeError("no ARM in this test")           # the definition stays unknown


def test_live_probe_against_a_fake_project_and_its_sanitised_export(server, tmp_path):
    FakeFoundry.sse = False
    endpoint = server + "/api/projects/proj/"
    raw = tmp_path / "export"
    run = foundry.live_runner(endpoint, token_provider=lambda: TOKEN, save_raw=raw,
                              az_runner=fake_az)
    env = foundry.probe(endpoint, "x", runner=run, save_raw=raw)
    validate_env(env.to_dict())
    agent = node(env, "principal/agent/x")["attrs"]
    assert agent["object_id"] == OID and agent["version"] == "2" and agent["a2a"] is True
    assert agent["env_vars"] == ["MODEL", "OPENAI_API_KEY"]            # names only
    assert agent["image"] == "https://acr.azurecr.io" and agent["agent_card_skills"] == ["s1"]
    assert agent["endpoint_protocols"] == ["responses", "a2a"]
    # declared tools with azd's ids, the remote allowed tool, the live MCP listing
    for node_id in ("toolbox/tools/code_interpreter", "toolbox/tools/azure_ai_search/search-conn",
                    "toolbox/tools/mcp/docs", "toolbox/tools/mcp/docs/microsoft_docs_search",
                    "toolbox/tools/mcp/code_interpreter", "toolbox/tools/mcp/azure_ai_search",
                    "toolbox/tools/mcp/microsoft_docs_search"):
        assert node_id in env.nodes, sorted(env.nodes)
    assert node(env, "toolbox/tools/mcp/docs")["attrs"]["server_url"] == "https://learn.microsoft.com"
    conn = node(env, "connection/search-conn")["attrs"]
    assert conn["category"] == "CognitiveSearch" and conn["auth_type"] == "ApiKey"
    assert conn["target"] == "https://s.search.windows.net" and conn["location"] == "eu"
    # the agent identity's RBAC, with the Foundry Agent Consumer role named
    role = node(env, f"role/{foundry.AGENT_CONSUMER_ROLE}")
    assert role["name"] == "Foundry Agent Consumer"
    assert role["attrs"]["role_name"] == "Foundry Agent Consumer"
    assert role["attrs"].get("definition_unknown") is True
    assert env.out_edges("principal/agent/x", "assigned")[0]["attrs"]["scope"] == PROJECT_SCOPE
    assert not env.is_unknown("role_assignments")
    # nothing sensitive in the graph or in the export
    text = json.dumps(env.to_dict())
    files = {p.name: p.read_text(encoding="utf-8") for p in raw.iterdir()}
    assert "manifest.json" in files and len(files) == 9             # 7 answers, 1 failure
    failed = json.loads(files[azure.raw_key(["az", "rest", "--method", "get", "--url",
                                             f"{azure.ARM}/subscriptions/s/providers/Microsoft."
                                             f"Authorization/roleDefinitions/"
                                             f"{foundry.AGENT_CONSUMER_ROLE}"
                                             f"?api-version={azure.ROLE_API}"])])
    assert failed["error"] == "no ARM in this test" and "output" not in failed
    for name, content in [("graph", text), *files.items()]:
        for secret in (TOKEN, "s3cr3t-value", "gpt-test", "SECRETVALUE", "alice@contoso.com",
                       "key=ZZZ", "api-key=QQQ", "Bearer"):
            assert secret not in content, (name, secret)
    saved = json.loads(files[azure.raw_key(["get", "/connections?api-version=v1"])])
    assert saved["output"]["value"][0]["credentials"] == {"type": "ApiKey"}
    assert saved["output"]["value"][0]["metadata"]["Owner"] == "<redacted>"
    saved = json.loads(files[azure.raw_key(["get", "/agents/x/versions/2?api-version=v1"])])
    assert saved["output"]["definition"]["environment_variables"] == {
        "OPENAI_API_KEY": "<redacted>", "MODEL": "<redacted>"}
    # the replay says the same, offline
    again = foundry.replay(raw)
    assert again.sources[0]["mode"] == "replay" and foundry.is_export(raw)
    assert again.to_dict()["nodes"] == env.to_dict()["nodes"]
    assert again.to_dict()["edges"] == env.to_dict()["edges"]
    assert again.unknown == env.unknown


def test_failures_are_unknowns_never_exceptions(server, tmp_path):
    endpoint = server + "/api/projects/proj"
    run = foundry.live_runner(endpoint, token_provider=lambda: "wrong", az_runner=fake_az)
    env = foundry.probe(endpoint, "x", runner=run)
    validate_env(env.to_dict())
    whats = {u["what"]: u["why"] for u in env.unknown}
    assert "HTTP 401" in whats["agent:x"] and "wrong" not in whats["agent:x"]
    assert "HTTP 401" in whats["toolboxes"] and "HTTP 401" in whats["connections"]
    assert "instance identity" in whats["role_assignments"]
    assert "principal/agent/x" in env.nodes                      # the node exists, unfilled
    missing = foundry.probe(endpoint, "x", runner=foundry.replay_runner(tmp_path), mode="replay")
    assert "not in the export" in {u["what"]: u["why"] for u in missing.unknown}["agent:x"]
    with pytest.raises(foundry.FoundryProbeError):
        foundry.replay(tmp_path)                                  # no manifest, no endpoint


def test_no_list_tools_and_as_user(server):
    endpoint = server + "/api/projects/proj"
    run = foundry.live_runner(endpoint, token_provider=lambda: TOKEN, az_runner=fake_az)
    env = foundry.probe(endpoint, "x", runner=run, list_tools=False)
    assert env.is_unknown("mcp_tools:toolbox/tools")
    assert "toolbox/tools/mcp/code_interpreter" not in env.nodes
    assert "toolbox/tools/code_interpreter" in env.nodes            # still declared
    env = foundry.probe(endpoint, "x", runner=run, as_user=True)
    assert node(env, "toolbox/tools/mcp/code_interpreter")["attrs"]["listed_as"] == "user"
    assert not env.is_unknown("mcp_tools_identity:toolbox/tools")


def test_sanitise_drops_secret_like_keys_everywhere():
    raw = {"accessToken": "t", "client_secret": "s", "Authorization": "Bearer x",
           "password": "p", "apiKey": "k", "credentials": {"type": "AAD", "key": "k"},
           "environment_variables": {"A": "1"}, "nested": [{"token": 1, "ok": "me@x.org"}],
           "keep": "value"}
    assert foundry.sanitise(raw) == {"credentials": {"type": "AAD"},
                                     "environment_variables": {"A": "<redacted>"},
                                     "nested": [{"ok": "<redacted>"}], "keep": "value"}
    assert foundry.sanitise({"credentials": "literal"}) == {}


# --------------------------------------------------------------------------
# CLI options (wired by skillc.cli)
# --------------------------------------------------------------------------

def parser(with_azure_opts: bool) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    if with_azure_opts:
        ap.add_argument("--save-raw", metavar="DIR")
        ap.add_argument("--from-raw", metavar="DIR")
    foundry.add_probe_opts(ap)
    return ap


def test_probe_opts_coexist_with_the_azure_options():
    for shared in (True, False):
        args = parser(shared).parse_args(["--foundry", "--project", "https://p/api/projects/x",
                                          "--agent", "a:3", "--no-list-tools", "--as-user",
                                          "--save-raw", "d", "--from-raw", "e"])
        assert args.foundry and args.agent == "a:3" and args.save_raw == "d"
        assert args.from_raw == "e" and args.no_list_tools and args.as_user
    assert foundry._split_agent("a:3") == ("a", "3") and foundry._split_agent("a") == ("a", None)
    assert foundry._split_agent(None) == (None, None)


def test_probe_from_args_replays_the_fixture_and_ignores_other_adapters():
    ap = parser(True)
    assert foundry.probe_from_args(ap.parse_args([])) is None
    assert foundry.probe_from_args(ap.parse_args(["--from-raw", str(FIXTURE.parent)])) is None
    env = foundry.probe_from_args(ap.parse_args(["--from-raw", str(FIXTURE)]))
    assert env is not None and AGENT in env.nodes                     # a foundry export
    env = foundry.probe_from_args(ap.parse_args(["--foundry", "--from-raw", str(FIXTURE),
                                                 "--no-list-tools"]))
    assert env.is_unknown("mcp_tools:toolbox/finance-tools")
    with pytest.raises(ValueError):
        foundry.probe_from_args(ap.parse_args(["--foundry"]))
