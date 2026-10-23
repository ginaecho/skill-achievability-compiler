"""The GitHub Copilot CLI runtime adapter and Copilot as skillc's default runtime."""
from __future__ import annotations

import json

import pytest

from skillc.cli import main
from skillc.env import copilot
from skillc.env.facts import need, possible_tools
from skillc.profiles import load_profile


@pytest.fixture
def home(tmp_path):
    """A Copilot configuration directory with approvals, saved URLs, MCP servers, trust."""
    home = tmp_path / "copilot-home"
    home.mkdir()
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    (home / "permissions-config.json").write_text(json.dumps({"locations": {
        str(repo): {"tool_approvals": [
            {"kind": "commands", "commandIdentifiers": ["git status", "python"]},
            {"kind": "write"}]},
        str(tmp_path / "elsewhere"): {"tool_approvals": [
            {"kind": "commands", "commandIdentifiers": ["rm"]}]}}}))
    (home / "settings.json").write_text(json.dumps({"allowedUrls": ["github.com"]}))
    (home / "mcp-config.json").write_text(json.dumps({"mcpServers": {
        "notes": {"command": "notes-server", "args": ["--stdio"]}}}))
    (home / "config.json").write_text(json.dumps({
        "trustedFolders": [str(tmp_path)], "auth": {"token": "never-read"}}))
    return home


def _probe(home, system="Windows", **kw):
    repo = home.parent / "repo"
    return copilot.probe(root=repo / "sub" if kw.pop("sub", False) else repo, home=home,
                         tools=copilot.default_tools(system), credentials=[],
                         check_egress=False, **kw)


def test_profile_lists_the_documented_built_in_tools():
    p = load_profile("copilot-cli")
    assert p.shell
    assert {"bash", "powershell", "view", "create", "edit", "grep", "glob", "web_fetch",
            "task", "ask_user", "skill", "apply_patch"} <= p.tools


def test_only_this_platforms_shell_is_a_tool():
    assert "powershell" in copilot.default_tools("Windows")
    assert "bash" not in copilot.default_tools("Windows")
    assert "read_bash" not in copilot.default_tools("Windows")
    assert "bash" in copilot.default_tools("Linux")
    assert "powershell" not in copilot.default_tools("Darwin")


def test_reads_run_without_asking_and_writes_ask_first(home, tmp_path):
    (home / "permissions-config.json").write_text("{}")
    env = _probe(home)
    assert need(env, {"tool": "view"}).value is True
    assert need(env, {"tool": "grep"}).value is True
    asked = need(env, {"tool": "powershell", "arg": "npm test"})
    assert asked.value is None and "asks" in asked.reasons[0]
    bash = need(env, {"tool": "bash"})                         # Windows' shell is powershell
    assert bash.value is None and "bash is powershell here" in bash.reasons[0]
    assert need(env, {"tool": "slack_send_message"}).value is False


def test_saved_approvals_apply_only_to_this_repository(home):
    env = _probe(home)
    assert need(env, {"tool": "powershell", "arg": "git status"}).value is True
    assert need(env, {"tool": "powershell", "arg": "python -m pytest"}).value is True
    assert need(env, {"tool": "powershell", "arg": "pythonx"}).value is None
    assert need(env, {"tool": "powershell", "arg": "rm -rf build"}).value is None
    assert need(env, {"tool": "edit"}).value is True             # a saved write approval
    assert need(env, {"tool": "web_fetch", "arg": "https://github.com/x"}).value is True


def test_approvals_are_keyed_by_the_git_root(home):
    env = _probe(home, sub=True)
    assert need(env, {"tool": "powershell", "arg": "git status"}).value is True


def test_mcp_servers_trust_and_unknowns(home):
    env = _probe(home)
    servers = {n["name"]: n for n in env.of_kind("mcp_server")}
    assert set(servers) == {"github", "notes"}
    assert servers["github"]["attrs"]["builtin"] is True
    assert env.is_unknown("mcp_tools:github") and env.is_unknown("mcp_tools:notes")
    assert env.is_unknown("deny_rules")
    root = next(n for n in env.of_kind("scope") if n["attrs"].get("level") == "path")
    assert root["attrs"]["trusted"] is True
    assert "never-read" not in json.dumps(env.to_dict())


def test_missing_configuration_is_not_an_error(tmp_path):
    env = copilot.probe(root=tmp_path, home=tmp_path / "none", credentials=[],
                        check_egress=False)
    assert need(env, {"tool": "view"}).value is True
    assert env.sources[0]["detail"] == "no Copilot settings files"


def test_any_shell_grants_the_bash_capability(home):
    tools = possible_tools(_probe(home))
    assert {"powershell", "bash", "view", "edit"} <= tools


def test_copilot_is_the_default_profile(tmp_path, capsys):
    # tools the skill uses but does not declare are judged against the profile
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: t\ndescription: Patch a file.\n---\n# T\n\n"
                     "Use `apply_patch` to change the file, then call `list_agents`.\n")
    assert main(["check", str(skill)]) == 0
    capsys.readouterr()
    assert main(["check", str(skill), "--profile", "claude-code"]) == 1
    assert "apply_patch" in capsys.readouterr().out


def test_reach_and_env_probe_default_to_copilot(tmp_path, monkeypatch, capsys):
    seen = []
    real = copilot.probe

    def fake(**kw):
        seen.append("copilot")
        return real(root=tmp_path, home=tmp_path / "none", credentials=[],
                    check_egress=False)

    monkeypatch.setattr(copilot, "probe", fake)
    skill = tmp_path / "SKILL.md"
    skill.write_text("---\nname: memo\ndescription: Write a memo.\n---\nBe concise.\n")
    assert main(["reach", str(skill)]) == 0
    out = tmp_path / "env.json"
    assert main(["env", "probe", "-o", str(out)]) == 0
    assert seen == ["copilot", "copilot"]
    assert json.loads(out.read_text())["sources"][0]["adapter"] == "copilot"


def test_monitor_init_installs_copilot_hooks_by_default(tmp_path):
    assert main(["monitor", "init", "--root", str(tmp_path)]) == 0
    hooks = json.loads((tmp_path / ".github" / "hooks" / "skillc.json").read_text())
    assert "preToolUse" in hooks["hooks"]
    claude_root = tmp_path / "claude"
    assert main(["monitor", "init", "--claude", "--root", str(claude_root)]) == 0
    assert not (claude_root / ".github").exists()
    assert (claude_root / ".skillc" / "monitor.json").exists()
