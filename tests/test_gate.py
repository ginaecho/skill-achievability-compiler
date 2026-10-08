"""The deploy gate: packs, skills and topology against a declared azure.yaml."""
from __future__ import annotations

import argparse
import json
import shutil
import textwrap
from pathlib import Path

import pytest

from skillc.frontend.runtime import load_runtime
from skillc.gate import (HOOK_SNIPPET, GateError, GateReport, cmd_gate, effective_runtime,
                         emit_verdict, gate)
from skillc.env.azd import from_azure_yaml

EXAMPLE = Path(__file__).parent.parent / "examples" / "hosted-agent-finance"
IGNORE = shutil.ignore_patterns("src", ".skillc", ".azure", "*.log", "__pycache__")


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """A throwaway copy of the finance example (without its source tree)."""
    dst = tmp_path / "finance"
    shutil.copytree(EXAMPLE, dst, ignore=IGNORE)
    return dst


def run(project: Path, declared: str = "azure.yaml", **extra) -> tuple[int, str]:
    ns = argparse.Namespace(dir=str(project), declared=declared, env=None,
                            runtime="foundry-hosted", json=False, install_hook=False)
    for key, value in extra.items():
        setattr(ns, key, value)
    import io
    import contextlib
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        rc = cmd_gate(ns)
    return rc, out.getvalue()


def entry(report: GateReport, kind: str, name: str):
    found = [e for e in report.entries if e.kind == kind and e.name == name]
    assert found, [(e.kind, e.name) for e in report.entries]
    return found[0]


# --------------------------------------------------------------------------
# The effective runtime
# --------------------------------------------------------------------------

def test_effective_runtime_base_withdraws_undeclared_tools():
    eff = effective_runtime(load_runtime("foundry-hosted"), from_azure_yaml(EXAMPLE / "azure.yaml"))
    assert sorted(eff.runtime.tools) == ["code_interpreter", "read", "web_fetch", "web_search",
                                         "write"]
    assert sorted(eff.withdrawn) == ["a2a", "mcp", "openapi", "search"]
    assert eff.withdrawn["search"] == ("not declared in azure.yaml: add `azure_ai_search` to a "
                                       "toolbox the agent uses")
    assert eff.fix_for("search") == "add `azure_ai_search` to a toolbox the agent uses"
    assert eff.assumptions == {}
    assert eff.runtime.grants == load_runtime("foundry-hosted").grants


def test_effective_runtime_search_keeps_search():
    eff = effective_runtime(load_runtime("foundry-hosted"),
                            from_azure_yaml(EXAMPLE / "azure.search.yaml"))
    assert "search" in eff.runtime.tools
    assert "search" not in eff.withdrawn


def test_effective_runtime_isolated_keeps_web_fetch_as_an_assumption():
    eff = effective_runtime(load_runtime("foundry-hosted"),
                            from_azure_yaml(EXAMPLE / "azure.isolated.yaml"))
    assert "web_fetch" in eff.runtime.tools
    assert "web_fetch" in eff.assumptions
    assert "AllowOnlyApprovedOutbound" in eff.assumptions["web_fetch"]


# --------------------------------------------------------------------------
# The example, configuration by configuration
# --------------------------------------------------------------------------

def test_base_is_achievable(project: Path):
    report = gate(project)
    assert report.verdict == "ACHIEVABLE" and report.exit_code == 0
    assert "search" in report.withdrawn_runtime_tools
    pack = entry(report, "pack", "quarterly_finance_report.ce")
    assert pack.verdict == "ACHIEVABLE"
    assert pack.detail["via"] == ["code_interpreter", "write"]   # the deployed pack needs no search
    assert pack.detail["withdrawn"] == {} and pack.detail["pruned"] == []
    assert sorted(e.name for e in report.skills) == sorted(
        ["ExpenseAnalyst.md", "Fetcher.md", "RevenueAnalyst.md", "TaxSpecialist.md",
         "TaxVerifier.md", "Writer.md"])
    assert all(e.verdict == "ACHIEVABLE" for e in report.skills)
    assert report.topology == [] and "single-agent" in report.topology_note
    rc, out = run(project)
    assert rc == 0
    assert out.rstrip().endswith("gate: ACHIEVABLE")
    assert "withdrawn search: not declared in azure.yaml: add `azure_ai_search` to a toolbox" in out


def test_search_is_achievable(project: Path):
    report = gate(project, declared="azure.search.yaml")
    assert report.verdict == "ACHIEVABLE"
    assert "search" in report.runtime_tools
    assert run(project, "azure.search.yaml")[0] == 0


def test_isolated_is_achievable_because_nothing_uses_web_fetch(project: Path):
    report = gate(project, declared="azure.isolated.yaml")
    assert "web_fetch" in report.runtime_assumptions
    assert report.verdict == "ACHIEVABLE"
    assert all(e.assumptions == [] for e in report.packs)
    rc, out = run(project, "azure.isolated.yaml")
    assert rc == 0 and "assumed web_fetch:" in out


def test_isolated_is_unknown_when_a_pack_uses_web_fetch(project: Path):
    ce = project / "protocol" / "quarterly_finance_report.ce"
    ce.write_text(ce.read_text(encoding="utf-8").replace(
        "Tool `fetch_financials` (owner `Fetcher`): via `code_interpreter`;",
        "Tool `fetch_financials` (owner `Fetcher`): via `web_fetch`;"), encoding="utf-8")
    assert gate(project).verdict == "ACHIEVABLE"           # open egress: no assumption
    report = gate(project, declared="azure.isolated.yaml")
    assert report.verdict == "UNKNOWN" and report.exit_code == 3
    pack = entry(report, "pack", "quarterly_finance_report.ce")
    assert pack.verdict == "UNKNOWN" and pack.assumptions and "`web_fetch`" in pack.assumptions[0]
    assert run(project, "azure.isolated.yaml")[0] == 3


def test_email_pack_flipped_in_is_impossible_naming_email_account(project: Path):
    shutil.copy(project / "protocol-variants" / "quarterly_finance_report.email.ce",
                project / "protocol")
    report = gate(project)
    assert report.verdict == "IMPOSSIBLE" and report.exit_code == 1
    pack = entry(report, "pack", "quarterly_finance_report.email.ce")
    assert pack.verdict == "IMPOSSIBLE"
    assert "`email_account`" in pack.reason and "`email_report`" in pack.reason
    assert pack.fixes[0].startswith("declare in azure.yaml a connection that provides "
                                    "`email_account` for `email_report`")
    assert entry(report, "pack", "quarterly_finance_report.ce").verdict == "ACHIEVABLE"
    rc, out = run(project)
    assert rc == 1 and out.rstrip().endswith("gate: IMPOSSIBLE")


def test_search_pack_flipped_in_is_impossible_under_base(project: Path):
    shutil.copy(project / "protocol-variants" / "quarterly_finance_report.search.ce",
                project / "protocol")
    report = gate(project)
    assert report.verdict == "IMPOSSIBLE"
    pack = entry(report, "pack", "quarterly_finance_report.search.ce")
    assert pack.verdict == "IMPOSSIBLE"
    assert "Tool `lookup_tax_rules` cannot run here: `search` is not declared" in pack.reason
    assert pack.fixes[0] == "add `azure_ai_search` to a toolbox the agent uses"
    assert pack.detail["withdrawn"] == {"lookup_tax_rules": "search"}
    assert pack.detail["pruned"] == ["RevenueAnalyst:HighRevenueNotification"]
    assert pack.detail["pure_verdict"] == "ACHIEVABLE"
    # the same project is fine once the toolbox declares the search tool
    assert gate(project, declared="azure.search.yaml").verdict == "ACHIEVABLE"
    rc, out = run(project)
    assert rc == 1 and "    fix: add `azure_ai_search` to a toolbox the agent uses" in out


def test_skill_with_undeclared_frontmatter_tool_is_impossible(project: Path):
    (project / "skills" / "Auditor.md").write_text(textwrap.dedent("""\
        ---
        name: auditor
        description: Reads the tax rules from the search index.
        tools: [azure_ai_search]
        ---
        # Auditor

        Query the tax-rules index and report what applies.
        """), encoding="utf-8")
    report = gate(project)
    assert report.verdict == "IMPOSSIBLE"
    skill = entry(report, "skill", "Auditor.md")
    assert skill.verdict == "IMPOSSIBLE"
    assert "frontmatter tool `azure_ai_search`" in skill.reason
    assert skill.fixes == ["add `azure_ai_search` to a toolbox the agent uses"]
    # declared in the search variant: the tool is no longer refused (the word "azure" still
    # reads as an Azure-account need the declaration cannot confirm, hence UNKNOWN, not refuted)
    search = entry(gate(project, declared="azure.search.yaml"), "skill", "Auditor.md")
    assert search.verdict != "IMPOSSIBLE"
    assert search.detail["frontmatter_tools_missing"] == []


def test_skill_frontmatter_runtime_tool_is_accepted(project: Path):
    (project / "skills" / "Filer.md").write_text(textwrap.dedent("""\
        ---
        name: filer
        description: Keeps the approvals under $HOME.
        tools: [write, code_interpreter]
        ---
        # Filer

        Record every approval as a file.
        """), encoding="utf-8")
    report = gate(project)
    assert entry(report, "skill", "Filer.md").verdict == "ACHIEVABLE"
    assert report.verdict == "ACHIEVABLE"


def test_email_skill_flipped_in_stays_achievable(project: Path):
    # its prose names no tool or connection the natural-language front-end refutes
    shutil.copy(project / "skills-variants" / "Writer.email.md", project / "skills")
    report = gate(project)
    assert entry(report, "skill", "Writer.email.md").verdict == "ACHIEVABLE"
    assert len(report.skills) == 7


# --------------------------------------------------------------------------
# Observed environment, report shape, CLI details
# --------------------------------------------------------------------------

def test_observed_env_is_merged_over_the_declaration(project: Path):
    declared = from_azure_yaml(project / "azure.search.yaml")
    observed = from_azure_yaml(project / "azure.search.yaml")
    node = observed.nodes["toolbox/finance-tools/azure_ai_search/tax-rules-search"]
    node["attrs"]["available"] = False                 # a probe found the tool missing
    node["attrs"]["declared"] = False
    (project / "observed.json").write_text(json.dumps(observed.to_dict()), encoding="utf-8")
    assert "search" in effective_runtime(load_runtime("foundry-hosted"), declared).runtime.tools
    report = gate(project, declared="azure.search.yaml", observed="observed.json")
    assert report.observed == "observed.json"
    assert "search" in report.withdrawn_runtime_tools


def test_to_dict_and_json_output(project: Path):
    report = gate(project)
    d = report.to_dict()
    assert d["schema"] == "skillc.gate/1"
    assert d["verdict"] == "ACHIEVABLE" and d["exit"] == 0
    assert d["withdrawn_runtime_tools"]["search"].startswith("not declared in azure.yaml")
    assert {e["name"] for e in d["packs"]} == {"quarterly_finance_report.ce"}
    assert len(d["skills"]) == 6 and d["topology"] == []
    assert json.loads(json.dumps(d)) == d
    rc, out = run(project, json=True)
    assert rc == 0 and json.loads(out)["verdict"] == "ACHIEVABLE"


def test_render_one_line_per_item_and_indented_fixes(project: Path):
    shutil.copy(project / "protocol-variants" / "quarterly_finance_report.search.ce",
                project / "protocol")
    text = gate(project).render()
    lines = text.splitlines()
    assert lines[0].startswith("runtime foundry-hosted (declared azure.yaml): ")
    assert sum(1 for ln in lines if ln.startswith("pack ")) == 2
    assert sum(1 for ln in lines if ln.startswith("skill ")) == 6
    assert any(ln.startswith("    fix: ") for ln in lines)
    assert lines[-1] == "gate: IMPOSSIBLE"


def test_install_hook_prints_snippet_without_gating(tmp_path: Path):
    rc, out = run(tmp_path / "missing", install_hook=True)
    assert rc == 0 and out == HOOK_SNIPPET
    assert "predeploy" in out and "skillc gate . --declared azure.yaml" in out


def test_errors_exit_2(tmp_path: Path, capsys, project: Path):
    assert run(tmp_path / "missing")[0] == 2
    assert "error" in capsys.readouterr().err
    (project / "protocol" / "broken.ce").write_text("not a CE document\n", encoding="utf-8")
    with pytest.raises(GateError):
        gate(project)
    assert run(project)[0] == 2
    (project / "protocol" / "broken.ce").unlink()
    assert run(project, runtime="no-such-runtime")[0] == 2


def test_emit_verdict_never_raises(project: Path):
    emit_verdict(gate(project))


# --------------------------------------------------------------------------
# Topology: two hosted agents talking over A2A
# --------------------------------------------------------------------------

TWO_AGENTS = """\
name: two-agents
services:
  ai-project:
    host: azure.ai.project
    endpoint: ${FOUNDRY_PROJECT_ENDPOINT}
  fetcher-to-writer:
    host: azure.ai.connection
    uses: [ai-project]
    category: RemoteA2A
    target: ${FOUNDRY_PROJECT_ENDPOINT}/agents/writer-agent/endpoint/protocols/a2a
    authType: AgenticIdentityToken
  fetcher-tools:
    host: azure.ai.toolbox
    uses: [ai-project, fetcher-to-writer]
    tools:
      - type: code_interpreter
      - type: a2a
        a2a_version: "1.0"
        connection: fetcher-to-writer
  writer-tools:
    host: azure.ai.toolbox
    uses: [ai-project]
    tools:
      - type: code_interpreter
  fetcher-skill:
    host: azure.ai.skill
    uses: [ai-project]
    instructions: ./skills/Fetcher.md
  writer-skill:
    host: azure.ai.skill
    uses: [ai-project]
    instructions: ./skills/Writer.md
  fetcher-agent:
    host: azure.ai.agent
    kind: hosted
    project: src/fetcher
    language: python
    uses: [ai-project, fetcher-tools, fetcher-skill]
    toolboxes:
      - name: fetcher-tools
    agentEndpoint:
      protocols: [responses]
  writer-agent:
    host: azure.ai.agent
    kind: hosted
    project: src/writer
    language: python
    uses: [ai-project, writer-tools, writer-skill]
    toolboxes:
      - name: writer-tools
    agentEndpoint:
      protocols: [responses, a2a]
"""

TWO_AGENT_PACK = """\
Skill `two-agent-report`.
Roles: `Fetcher`, `Writer`.
Tool `fetch` (owner `Fetcher`): via `code_interpreter`; adds `fetched`; effect `local`.
Tool `write_report` (owner `Writer`): via `write`; requires `fetched`; adds `written`; effect `local`.
Initially true: none.
Goal: `written`.
Protocol:
  - `Fetcher` uses `fetch`.
  - `Fetcher` tells `Writer` `Data`.
  - `Writer` uses `write_report`.
  - `Writer` tells `Fetcher` `Done`.
"""


@pytest.fixture
def two_agents(tmp_path: Path) -> Path:
    root = tmp_path / "two"
    (root / "protocol").mkdir(parents=True)
    (root / "skills").mkdir()
    (root / "azure.yaml").write_text(TWO_AGENTS, encoding="utf-8")
    (root / "protocol" / "report.ce").write_text(TWO_AGENT_PACK, encoding="utf-8")
    for role in ("Fetcher", "Writer"):
        (root / "skills" / f"{role}.md").write_text(
            f"---\nname: {role.lower()}\ndescription: {role} role.\n---\n# {role}\n\nDo the work.\n",
            encoding="utf-8")
    return root


def test_two_agents_missing_return_edge_is_impossible(two_agents: Path):
    report = gate(two_agents)
    assert report.verdict == "IMPOSSIBLE"
    assert "a2a" in report.runtime_tools                    # fetcher-tools declares it
    assert "2 agents declared" in report.topology_note
    forward = entry(report, "topology", "report.ce: Fetcher -> Writer (Data)")
    assert forward.verdict == "ACHIEVABLE"
    assert "over connection fetcher-to-writer" in forward.reason
    assert forward.assumptions and "Foundry Agent Consumer" in forward.assumptions[0]
    back = entry(report, "topology", "report.ce: Writer -> Fetcher (Done)")
    assert back.verdict == "IMPOSSIBLE"
    assert "no RemoteA2A connection targets /agents/fetcher-agent/endpoint/protocols/a2a" \
        in back.reason
    assert "agent fetcher-agent does not expose a2a on its endpoint" in back.reason
    assert back.fixes[0] == ("declare an azure.ai.connection `writer-agent-to-fetcher-agent` "
                             "with category RemoteA2A, authType AgenticIdentityToken and target "
                             "<project endpoint>/agents/fetcher-agent/endpoint/protocols/a2a")
    assert "add `a2a` to agentEndpoint.protocols of agent fetcher-agent" in back.fixes
    assert run(two_agents)[0] == 1


def test_two_agents_complete_topology_is_achievable_under_assumption(two_agents: Path):
    text = (two_agents / "azure.yaml").read_text(encoding="utf-8")
    text = text.replace("""  fetcher-tools:
    host: azure.ai.toolbox
    uses: [ai-project, fetcher-to-writer]
""", """  writer-to-fetcher:
    host: azure.ai.connection
    uses: [ai-project]
    category: RemoteA2A
    target: ${FOUNDRY_PROJECT_ENDPOINT}/agents/fetcher-agent/endpoint/protocols/a2a
    authType: AgenticIdentityToken
  fetcher-tools:
    host: azure.ai.toolbox
    uses: [ai-project, fetcher-to-writer]
""").replace("""  writer-tools:
    host: azure.ai.toolbox
    uses: [ai-project]
    tools:
      - type: code_interpreter
""", """  writer-tools:
    host: azure.ai.toolbox
    uses: [ai-project, writer-to-fetcher]
    tools:
      - type: code_interpreter
      - type: a2a
        a2a_version: "1.0"
        connection: writer-to-fetcher
""").replace("""    agentEndpoint:
      protocols: [responses]
""", """    agentEndpoint:
      protocols: [responses, a2a]
""")
    (two_agents / "azure.yaml").write_text(text, encoding="utf-8")
    report = gate(two_agents)
    assert [e.verdict for e in report.topology] == ["ACHIEVABLE", "ACHIEVABLE"]
    assert all(e.verdict == "ACHIEVABLE" for e in report.packs + report.skills)
    # the Foundry Agent Consumer role lives outside azure.yaml: recorded as an assumption on
    # each edge, not a reason to hold the deploy (the control-plane probe observes it later)
    assert all("Foundry Agent Consumer" in e.assumptions[0] for e in report.topology)
    assert report.verdict == "ACHIEVABLE" and run(two_agents)[0] == 0


def test_two_agents_missing_toolbox_tool_names_the_toolbox_edit(two_agents: Path):
    text = (two_agents / "azure.yaml").read_text(encoding="utf-8")
    text = text.replace("""      - type: a2a
        a2a_version: "1.0"
        connection: fetcher-to-writer
""", "")
    (two_agents / "azure.yaml").write_text(text, encoding="utf-8")
    report = gate(two_agents)
    forward = entry(report, "topology", "report.ce: Fetcher -> Writer (Data)")
    assert forward.verdict == "IMPOSSIBLE"
    assert "has an a2a tool over connection fetcher-to-writer" in forward.reason
    assert forward.fixes[0] == ("add `- type: a2a` with `a2a_version: \"1.0\"` and "
                                "`connection: fetcher-to-writer` to a toolbox agent "
                                "fetcher-agent uses")
    assert "a2a" in report.withdrawn_runtime_tools


def test_two_agents_unmapped_role_is_unknown(two_agents: Path):
    (two_agents / "skills" / "Writer.md").rename(two_agents / "skills" / "Author.md")
    text = (two_agents / "azure.yaml").read_text(encoding="utf-8")
    (two_agents / "azure.yaml").write_text(text.replace("./skills/Writer.md", "./skills/Author.md"),
                                           encoding="utf-8")
    report = gate(two_agents)
    back = entry(report, "topology", "report.ce: Writer -> Fetcher (Done)")
    assert back.verdict == "UNKNOWN" and "role `Writer` maps to no declared agent" in back.reason
    assert report.verdict == "UNKNOWN"
