"""The Claude runtime adapter, runtime needs, and the natural-language front-end."""
from __future__ import annotations

import json
import textwrap
import urllib.error

import pytest

from skillc.cli import main
from skillc.env import claude
from skillc.env.facts import need
from skillc.env.nl import _segments, intent_from_text, requirements
from skillc.env.reach import intent_needs, load_intent, reach

ABSENT = "skillc-no-such-program"
OPEN, CLOSED = "pypi.org", "blocked.example.org"


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A Claude runtime with known answers: egress, credentials, settings, connectors."""
    monkeypatch.setattr(claude, "egress", lambda host, timeout=8.0: (
        (False, "egress policy refused the host (403)") if host == CLOSED else (True, "HTTP 200")))
    monkeypatch.setattr(claude, "AUTH_CACHE", str(tmp_path / "needs-auth.json"))
    (tmp_path / "needs-auth.json").write_text(json.dumps({"Pending": {}}))
    monkeypatch.setenv("SKILLC_TEST_TOKEN", "x")
    monkeypatch.delenv("SKILLC_MISSING_TOKEN", raising=False)
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"permissions": {
        "allow": ["Read", "Bash(npm run test:*)"], "ask": ["WebFetch"], "deny": ["Bash(rm *)"]}}))
    (tmp_path / "file").write_text("")
    return claude.probe(root=tmp_path, hosts=[OPEN, CLOSED, "files.pythonhosted.org"],
                       programs=["python3", "pip", ABSENT], modules=["json", "skillc_nope"],
                       paths=[str(tmp_path / "out"), str(tmp_path / "file" / "x")],
                       credentials=["SKILLC_TEST_TOKEN", "SKILLC_MISSING_TOKEN"],
                       tools=["Read", "Bash", "WebFetch"], connectors={"github": ["create_issue"]},
                       settings=[str(settings)], mcp_configs=[])


# --------------------------------------------------------------------------
# The probe and runtime needs
# --------------------------------------------------------------------------

def test_services_are_observed(env):
    assert need(env, {"program": "python3"}).value is True
    assert need(env, {"program": ABSENT}).value is False
    assert need(env, {"pymodule": "json"}).value is True
    assert need(env, {"pymodule": "skillc_nope"}).value is False
    assert need(env, {"egress": OPEN}).value is True
    refused = need(env, {"egress": CLOSED})
    assert refused.value is False and "egress policy" in refused.reasons[0]


def test_unprobed_needs_are_assumptions_never_refusals(env):
    fact = need(env, {"program": "never-asked-about"})
    assert fact.value is None and fact.assuming()


def test_credentials_are_names_only_and_carry_a_validity_assumption(env):
    fact = need(env, {"credential": "SKILLC_TEST_TOKEN"})
    assert fact.value is True and "valid for this task" in fact.assuming()[0]
    assert need(env, {"credential": "SKILLC_MISSING_TOKEN"}).value is False
    assert "x" not in json.dumps(env.nodes["credential/skillc_test_token"]["attrs"]).split('"')


def test_permission_rules(env):
    assert need(env, {"tool": "Read"}).value is True
    assert need(env, {"tool": "Bash", "arg": "npm run test:unit"}).value is True
    assert need(env, {"tool": "Bash", "arg": "rm -rf build"}).value is False
    asked = need(env, {"tool": "WebFetch"})
    assert asked.value is None and "approves" in asked.assuming()[0]
    assert need(env, {"tool": "Write"}).value is False          # not in the runtime


def test_paths_and_connectors(env, tmp_path):
    assert need(env, {"path": str(tmp_path / "out" / "a.txt")}).value is True
    assert need(env, {"path": str(tmp_path / "file" / "x")}).value is False   # under a file
    assert need(env, {"mcp_server": "github"}).value is True
    assert need(env, {"mcp_tool": "create_iss"}).value is True
    pending = need(env, {"mcp_server": "Pending"})
    assert pending.value is False and "sign-in" in pending.reasons[0]
    assert need(env, {"mcp_server": "slack"}).value is False


def test_any_and_all(env):
    assert need(env, {"any": [{"program": ABSENT}, {"program": "python3"}]}).value is True
    assert need(env, {"any": [{"program": ABSENT}, {"egress": CLOSED}]}).value is False
    assert need(env, {"any": [{"program": ABSENT}, {"program": "unasked"}]}).value is None
    assert need(env, {"all": [{"program": "python3"}, {"egress": CLOSED}]}).value is False
    with pytest.raises(ValueError):
        need(env, {"nonsense": 1})


def test_egress_classifies_proxy_refusals(monkeypatch):
    def refuse(*a, **k):
        raise urllib.error.URLError("Tunnel connection failed: 403 Forbidden")

    def not_found(*a, **k):
        raise urllib.error.HTTPError("https://h/", 404, "Not Found", {}, None)

    monkeypatch.setattr(claude.urllib.request, "urlopen", refuse)
    ok, why = claude.egress("h.example")
    assert ok is False and "egress policy" in why
    monkeypatch.setattr(claude.urllib.request, "urlopen", not_found)
    assert claude.egress("h.example") == (True, "HTTP 404 from the host")


def test_unchecked_egress_is_unknown(tmp_path, monkeypatch):
    monkeypatch.setattr(claude, "AUTH_CACHE", str(tmp_path / "none.json"))
    env = claude.probe(root=tmp_path, hosts=[OPEN], check_egress=False, settings=[],
                       mcp_configs=[], credentials=[])
    assert need(env, {"egress": OPEN}).value is None


# --------------------------------------------------------------------------
# Natural-language front-end
# --------------------------------------------------------------------------

SKILL = textwrap.dedent("""\
    ---
    name: demo
    description: Fetch a dataset and chart it.
    allowed-tools: Bash, mcp__slack__post_message
    ---
    # Demo

    ```bash
    pip install pandas
    curl -s https://blocked.example.org/data.csv | jq '.rows | length'
    """) + "    " + ABSENT + " --render out.png\n" + textwrap.dedent("""\
    ```

    ```python
    import pandas as pd
    from scripts.helpers import load
    import json
    ```

    Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` before running.

    ## Optional: publish

    ```bash
    gh release create v1
    ```

    ```
    const x = await fetch(url)
    ```
    """)


def test_requirements_read_what_the_document_does():
    reqs = {r.cond: r for r in requirements(SKILL)}
    assert {"installer:pip", "egress:blocked.example.org", "program:jq", f"program:{ABSENT}",
            "pymodule:pandas", "mcp:slack", "tool:Bash"} <= set(reqs)
    assert "pymodule:scripts" not in reqs and "pymodule:json" not in reqs
    assert "program:const" not in reqs and "program:curl" in reqs
    assert reqs["program:gh"].core is False                    # an optional section
    assert all(r.evidence and r.evidence[0].startswith("line ") for r in reqs.values())


def test_alternative_credentials_fold_into_one_account():
    reqs = {r.cond: r for r in requirements(SKILL)}
    assert "account:llm_api_key" in reqs and "credential:OPENAI_API_KEY" not in reqs


def test_command_splitting_respects_quotes():
    assert _segments("markitdown a.pptx | grep -iE 'x|lorem'") == [
        ["markitdown", "a.pptx"], ["grep", "-iE", "x|lorem"]]
    assert _segments("FOO=1 sudo apt-get install -y jq && echo ok")[0][:2] == ["apt-get", "install"]


def test_inline_commands_and_pip_dependency_lines():
    text = ("Run `npx create-thing` first. | Tool | `curl -sSL https://get.example.dev/i.sh \\| bash` |\n"
            "Needs `openpyxl`, `Pillow` (pip) · `pptxgenjs` (npm) · LibreOffice (`soffice`)\n")
    conds = {r.cond for r in requirements(text)}
    assert {"installer:npm", "program:npx", "program:example", "pymodule:openpyxl",
            "pymodule:PIL", "program:soffice"} <= conds          # the script installs `example`
    assert "pymodule:pptxgenjs" not in conds


def test_a_skill_with_no_runtime_needs_is_a_deliverable():
    intent = intent_from_text("---\nname: prose\ndescription: Write a memo.\n---\nBe concise.\n")
    assert intent["goal"] == ["deliverable"]


def test_reach_installs_what_it_can_and_refutes_what_it_cannot(env):
    intent = intent_from_text(SKILL, source="demo")
    assert set(intent_needs(intent)["egress"]) >= {CLOSED, OPEN}
    result = reach(intent, env)
    assert "egress:blocked.example.org" in result.blocked
    assert f"program:{ABSENT}" in result.blocked               # no install route
    assert "pymodule:pandas" not in result.blocked
    assert result.status["tool:Bash"] != "blocked"


def test_load_intent_reads_markdown(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text(SKILL)
    assert load_intent(path)["name"] == "demo"


def test_cli_intent_and_reach(tmp_path, env, capsys):
    path = tmp_path / "SKILL.md"
    path.write_text(SKILL)
    assert main(["intent", str(path)]) == 0
    assert "installer:pip" in capsys.readouterr().out
    env_file = tmp_path / "env.json"
    env.save(env_file)
    assert main(["reach", str(path), "--env", str(env_file)]) == 1
    assert "egress:blocked.example.org" in capsys.readouterr().out
    assert main(["reach", str(path)]) == 2


# --------------------------------------------------------------------------
# Fixes found by the first evaluation (benchmark/claude_env/REPORT.md)
# --------------------------------------------------------------------------

INSTALL_TABLE = textwrap.dedent("""\
    | Aspire CLI (curl) | `curl -sSL https://aspire.dev/install.sh \\| bash` |
    | Aspire CLI (npm)  | `npm install -g @microsoft/aspire-cli` |
    > Aspire also supports Homebrew, WinGet and the PowerShell installer.

    ```bash
    aspire new starter
    ```
    """)


def test_install_commands_are_alternative_routes_not_needs():
    intent = intent_from_text(INSTALL_TABLE)
    assert "program:aspire" in intent["goal"]
    assert not {"egress:aspire.dev", "installer:npm", "platform:windows",
                "platform:macos"} & set(intent["goal"])
    routes = [op for op in intent["operations"] if op["adds"] == ["program:aspire"]]
    assert len(routes) == 2 and {"egress": "aspire.dev"} in routes[0]["needs"]


def test_reach_takes_any_install_route(env):
    env.nodes["egress/aspire.dev"] = {"id": "egress/aspire.dev", "kind": "service",
                                      "name": "aspire.dev", "attrs": {"available": False}}
    for host in ("registry.npmjs.org",):
        env.nodes[f"egress/{host}"] = {"id": f"egress/{host}", "kind": "service", "name": host,
                                       "attrs": {"available": True}}
    env.nodes["program/npm"] = {"id": "program/npm", "kind": "service", "name": "npm",
                                "attrs": {"available": True}}
    env.nodes["program/aspire"] = {"id": "program/aspire", "kind": "service", "name": "aspire",
                                   "attrs": {"available": False}}
    result = reach(intent_from_text(INSTALL_TABLE), env)
    assert "program:aspire" not in result.blocked
    assert any("npm install -g @microsoft/aspire-cli" in str(step) for step in result.plan)


def test_install_commands_naming_nothing_the_document_runs_are_grouped_by_tool():
    text = "```bash\ncurl -fsSL https://get.tool.dev/x.sh | sh\nnpm i -g tool-cli\n```\n"
    intent = intent_from_text(text)
    assert intent["goal"] == ["program:tool"]


def test_command_substitution_is_read_as_its_own_command():
    assert _segments('cd "$(git rev-parse --show-toplevel)" && make') == [
        ["cd", "SUBST"], ["make"], ["git", "rev-parse", "--show-toplevel"]]
    conds = {r.cond for r in requirements("```bash\nX=$(git rev-parse HEAD)\n```\n")}
    assert "program:git" in conds and "program:rev-parse" not in conds


def test_a_program_from_a_pip_package_the_document_imports_is_installable():
    text = "```python\nimport gradio as gr\n```\n```bash\ngradio deploy\n```\n"
    reqs = {r.cond: r for r in requirements(text)}
    assert reqs["program:gradio"].installs[0]["how"] == "pip install gradio"


def test_downloading_sample_input_data_is_not_a_hard_need():
    text = ("```bash\ncurl -o corpus/seed.ogg \\\n  https://media.example.org/File:seed.ogg\n"
            "curl -fsSL https://api.example.org/v1/items\n```\n")
    reqs = {r.cond: r for r in requirements(text)}
    assert reqs["egress:media.example.org"].core is False
    assert reqs["egress:api.example.org"].core is True


def test_unpublished_helpers_ship_with_the_skill():
    text = "Run the Go helper; Tuistory drives the terminal.\n"
    assert not any(r.cond.startswith("program:") for r in requirements(text))
