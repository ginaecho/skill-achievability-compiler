"""The azd adapter: the environment an azure.yaml declares, offline."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from skillc.cli import main
from skillc.env.azd import AzdError, from_azure_yaml, intent_artifacts
from skillc.env.facts import need, policy_allows, tools_matching
from skillc.env.model import Environment, validate_env

AZD = Path(__file__).parent / "fixtures" / "azd"
BASIC = AZD / "01-basic" / "azure.yaml"
TOOLBOX = AZD / "04-foundry-toolbox" / "azure.yaml"
ISOLATED = AZD / "isolated-search" / "azure.yaml"


@pytest.fixture(scope="module")
def basic() -> Environment:
    return from_azure_yaml(BASIC)


@pytest.fixture(scope="module")
def toolbox() -> Environment:
    return from_azure_yaml(TOOLBOX)


@pytest.fixture(scope="module")
def isolated() -> Environment:
    return from_azure_yaml(ISOLATED)


def node(env: Environment, node_id: str) -> dict:
    assert node_id in env.nodes, sorted(env.nodes)
    return env.nodes[node_id]


# --------------------------------------------------------------------------
# Validity and provenance
# --------------------------------------------------------------------------

@pytest.mark.parametrize("path", [BASIC, TOOLBOX, ISOLATED])
def test_result_is_a_valid_declared_environment(path):
    env = from_azure_yaml(path)
    doc = env.to_dict()
    validate_env(doc)
    again = Environment.from_dict(doc)
    assert again.to_dict()["nodes"] == doc["nodes"]
    assert env.sources == [{"adapter": "azd", "mode": "declared", "detail": str(path.resolve())}]
    assert all(n["attrs"].get("declared") is True for n in env.nodes.values())
    assert node(env, "/")["attrs"]["level"] == "root"


def test_walk_is_deterministic():
    a, b = from_azure_yaml(ISOLATED).to_dict(), from_azure_yaml(ISOLATED).to_dict()
    a.pop("captured_at"), b.pop("captured_at")
    assert a == b


def test_unreadable_file_is_an_error(tmp_path):
    with pytest.raises(AzdError):
        from_azure_yaml(tmp_path / "missing.yaml")
    bad = tmp_path / "azure.yaml"
    bad.write_text("- just\n- a list\n", encoding="utf-8")
    with pytest.raises(AzdError):
        from_azure_yaml(bad)


# --------------------------------------------------------------------------
# Project: models and egress
# --------------------------------------------------------------------------

def test_model_deployment_becomes_an_available_declared_service(basic):
    model = node(basic, "model/gpt-5.4-mini")
    assert model["kind"] == "service" and model["attrs"]["type"] == "model"
    assert model["attrs"]["available"] is True
    assert model["attrs"]["version"] == "2026-03-17" and model["attrs"]["sku"] == "GlobalStandard"


def test_open_egress_is_declared_but_unknown_until_measured(basic):
    egress = node(basic, "egress/public")
    assert egress["attrs"]["mode"] == "AllowInternetOutbound"
    assert egress["attrs"]["isolated"] is False
    assert "available" not in egress["attrs"]
    assert basic.is_unknown("egress")
    fact = need(basic, {"egress": "pypi.org"})
    assert fact.value is None and fact.possible


def test_isolated_egress_is_unknown_never_refused(isolated):
    egress = node(isolated, "egress/public")
    assert egress["attrs"]["mode"] == "AllowOnlyApprovedOutbound"
    assert egress["attrs"]["isolated"] is True and egress["attrs"]["agent_subnet"] is True
    why = next(u["why"] for u in isolated.unknown if u["what"] == "egress")
    assert "network-isolated" in why
    assert need(isolated, {"egress": "pypi.org"}).value is None


# --------------------------------------------------------------------------
# Connections: never a credential value
# --------------------------------------------------------------------------

def test_connection_carries_category_auth_type_and_host_only(toolbox):
    conn = node(toolbox, "connection/ghmcppat")
    assert conn["attrs"]["category"] == "RemoteTool"
    assert conn["attrs"]["auth_type"] == "CustomKeys"
    assert conn["attrs"]["target"] == "https://api.githubcopilot.com"    # no path
    assert "credentials" not in conn["attrs"] and "keys" not in conn["attrs"]
    assert "Bearer" not in json.dumps(conn)
    assert toolbox.is_unknown("value:GITHUB_MCP_PAT")
    assert toolbox.is_unknown("value:AZURE_LANGUAGE_MCP_ENDPOINT")
    assert node(toolbox, "connection/langmcpconn")["attrs"].get("target") is None  # ${VAR}


def test_literal_credential_values_never_enter_the_graph(isolated):
    text = json.dumps(isolated.to_dict())
    assert "ABC123" not in text and "XYZ789" not in text
    conn = node(isolated, "connection/search-conn")
    assert conn["attrs"]["target"] == "https://contoso-search.search.windows.net"
    assert conn["attrs"]["env_vars"] == ["SEARCH_API_KEY"]            # the name, not the value
    assert isolated.is_unknown("value:SEARCH_API_KEY")
    assert node(isolated, "connection/docs-mcp")["attrs"]["target"] == "https://learn.microsoft.com"


# --------------------------------------------------------------------------
# Toolboxes and tools
# --------------------------------------------------------------------------

def test_toolbox_tools_carry_type_and_connection(toolbox):
    server = node(toolbox, "toolbox/agent-tools")
    assert server["kind"] == "mcp_server" and server["attrs"]["transport"] == "toolbox"
    exposed = {toolbox.nodes[e["dst"]]["id"] for e in toolbox.out_edges(server["id"], "exposes")}
    assert {"toolbox/agent-tools/web_search", "toolbox/agent-tools/code_interpreter",
            "toolbox/agent-tools/mcp/noauth_mcp", "toolbox/agent-tools/mcp/ghmcppat",
            "toolbox/agent-tools/mcp/langmcpconn",
            "toolbox/agent-tools/mcp/foundrymcpconn"} == exposed
    github = node(toolbox, "toolbox/agent-tools/mcp/ghmcppat")
    assert github["attrs"]["type"] == "mcp" and github["attrs"]["connection"] == "ghmcppat"
    assert github["attrs"]["server_url"] == "https://api.githubcopilot.com"
    assert node(toolbox, "toolbox/agent-tools/web_search")["name"] == "web_search"
    assert toolbox.is_unknown("mcp_tools:toolbox/agent-tools/mcp/ghmcppat")


def test_connected_mcp_server_without_a_tool_list_is_an_assumption(toolbox):
    fact = need(toolbox, {"mcp_tool": "create_issue"})
    assert fact.value is None and fact.possible and fact.assuming()


def test_declared_allowed_tools_are_tool_nodes(isolated):
    remote = node(isolated, "toolbox/research-tools/mcp/docs-mcp/microsoft_docs_search")
    assert remote["name"] == "microsoft_docs_search"
    assert need(isolated, {"mcp_tool": "microsoft_docs_search"}).value is True
    assert not isolated.is_unknown("mcp_tools:toolbox/research-tools/mcp/docs-mcp")
    assert isolated.is_unknown("mcp_tools:toolbox/research-tools/mcp/gitmcp")


def test_a_required_tool_is_found_where_declared_and_absent_elsewhere(isolated, toolbox, basic):
    assert [t["name"] for t in tools_matching(isolated, ["^azure_ai_search$"])] == ["azure_ai_search"]
    assert node(isolated, "toolbox/research-tools/azure_ai_search/search-conn")["attrs"]["connection"] == "search-conn"
    assert tools_matching(toolbox, ["^web_search$"])
    assert tools_matching(basic, ["^azure_ai_search$"]) == []           # absent, not refuted
    assert tools_matching(basic, ["^web_search$"]) == []
    assert basic.of_kind("mcp_server") == []


# --------------------------------------------------------------------------
# Agents and policies
# --------------------------------------------------------------------------

def test_agent_is_the_principal_with_sandbox_attrs_and_env_names_only(toolbox):
    agent = node(toolbox, "principal/agent/agent-framework-agent-with-foundry-toolbox-responses")
    a = agent["attrs"]
    assert a["type"] == "agent" and a["identity_mode"] == "agent" and a["agent_kind"] == "hosted"
    assert a["protocols"] == ["responses 2.0.0"]
    assert a["cpu"] == "0.5" and a["memory"] == "1Gi"
    assert a["env_vars"] == ["AZURE_AI_MODEL_DEPLOYMENT_NAME", "TOOLBOX_ENDPOINT"]
    assert a["toolboxes"] == ["agent-tools"]                 # from `uses`, a declared toolbox
    assert toolbox.principal()["id"] == agent["id"]


def test_ref_include_is_resolved_relative_to_the_file(isolated):
    agent = node(isolated, "principal/agent/researcher")
    a = agent["attrs"]
    assert a["agent_kind"] == "hosted" and a["cpu"] == "1.0" and a["memory"] == "2Gi"
    assert a["protocols"] == ["responses 2.0.0", "a2a 0.3.0"]
    assert a["description"] == "overrides the description in the include"
    assert a["toolboxes"] == ["research-tools", "undeclared-tools"]
    assert node(isolated, "toolbox/undeclared-tools")["kind"] == "mcp_server"
    assert isolated.is_unknown("mcp_tools:toolbox/undeclared-tools")


def test_remote_and_cyclic_refs_are_unknown_not_exceptions(isolated):
    whats = {u["what"]: u["why"] for u in isolated.unknown}
    assert "not fetched" in whats["ref:https://example.invalid/agent.yaml"]
    assert "cyclic" in whats["ref:./cycle-a.yaml"]
    assert node(isolated, "principal/agent/remote-include")["attrs"]["agent_kind"] == "prompt"
    assert node(isolated, "principal/agent/cycle-include")["attrs"]["agent_kind"] == "hosted"
    assert "unsupported host containerapp" in whats["service:legacy-web"]


def test_rai_policy_is_an_uninterpreted_deny(isolated):
    first = node(isolated, "policy/rai_policy/0")
    assert first["attrs"]["effect"] == "deny" and first["attrs"]["enforced"] is True
    assert first["attrs"]["rule"] == {"kind": "rai_policy", "values": ["${RAI_POLICY_NAME}"]}
    assert isolated.is_unknown("value:RAI_POLICY_NAME")
    second = node(isolated, "policy/rai_policy/1")
    assert second["attrs"]["rule"]["values"] == ["Microsoft.DefaultV2"]
    assert [e["dst"] for e in isolated.out_edges(first["id"], "applies")] == ["/"]
    fact = policy_allows(isolated, "Microsoft.Search/searchServices", "eastus", "/")
    assert fact.value is None and fact.possible and fact.assuming()


# --------------------------------------------------------------------------
# Intent artifacts
# --------------------------------------------------------------------------

def test_intent_artifacts_lists_skills_and_file_instructions():
    root = ISOLATED.parent.resolve()
    assert intent_artifacts(ISOLATED) == [
        root / "skills" / "cite-sources.md",            # azure.ai.skill
        root / "agents" / "researcher-prompt.md",       # agent instructions that is a file
    ]
    assert intent_artifacts(BASIC) == []


def test_intent_artifacts_adds_the_skills_directory(tmp_path):
    (tmp_path / "azure.yaml").write_text(BASIC.read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "a.md").write_text("# a\n", encoding="utf-8")
    (tmp_path / "skills" / "notes.txt").write_text("x\n", encoding="utf-8")
    assert intent_artifacts(tmp_path / "azure.yaml") == [(tmp_path / "skills" / "a.md").resolve()]


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_from_azd_writes_and_prints(tmp_path, capsys):
    out = tmp_path / "env.json"
    assert main(["env", "from-azd", str(ISOLATED), "-o", str(out)]) == 0
    captured = capsys.readouterr()
    assert f"wrote {out}" in captured.out
    assert "cite-sources.md" in captured.err
    loaded = Environment.load(out)
    assert loaded.sources[0]["adapter"] == "azd"
    assert "toolbox/research-tools/azure_ai_search/search-conn" in loaded.nodes
    assert main(["env", "show", str(out)]) == 0
    assert "mcp server 'research-tools'" in capsys.readouterr().out


def test_cli_from_azd_json_round_trip_via_subprocess():
    p = subprocess.run([sys.executable, "-m", "skillc.cli", "env", "from-azd", str(TOOLBOX),
                        "--json"], capture_output=True, text=True, encoding="utf-8")
    assert p.returncode == 0, p.stderr
    doc = json.loads(p.stdout)
    validate_env(doc)
    env = Environment.from_dict(doc)
    assert "toolbox/agent-tools/web_search" in env.nodes
    assert "intent artifacts: (none)" in p.stderr
    assert "Bearer" not in p.stdout


def test_cli_from_azd_missing_file_exits_2(tmp_path, capsys):
    assert main(["env", "from-azd", str(tmp_path / "nope.yaml")]) == 2
    assert "error" in capsys.readouterr().err
