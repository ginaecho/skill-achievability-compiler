"""Tools that do the same job under different names (skillc.equivalents)."""
from skillc.equivalents import groups, match, same_tool
from skillc.frontend.contracts import bind_environment
from skillc.frontend.grants import bind_grants
from skillc.profiles import load_profile

PACK = {"name": "book", "roles": ["agent"],
        "capabilities": {"ask_user_input_v0": {"owner": "agent", "add": ["chosen"]},
                         "web_search": {"owner": "agent", "pre": "chosen", "add": ["booked"]}},
        "protocol": [{"act": {"cap": "ask_user_input_v0", "by": "agent"}},
                     {"act": {"cap": "web_search", "by": "agent"}}],
        "goal": "booked"}


def test_each_name_is_in_at_most_one_group():
    seen = {}
    for does, names in groups():
        for n in names:
            assert n not in seen, f"{n} is in '{seen.get(n)}' and '{does}'"
            seen[n] = does


def test_match_prefers_the_exact_name_then_an_equivalent():
    assert match("web_search", ["web_search", "websearch"]) == "web_search"
    assert match("AskUserQuestion", ["ask_user"]) == "ask_user"
    assert match("slack_send_message", ["ask_user", "bash"]) is None
    assert same_tool("unknown_tool") == {"unknown_tool"}


def test_binding_counts_equivalents_unless_exact_names_are_asked_for():
    copilot = sorted(load_profile("copilot-cli").tools)
    exact = bind_grants(PACK, copilot, equivalents=False)
    assert exact.unavailable == ("ask_user_input_v0",) and exact.matched == ()
    loose = bind_environment(PACK, copilot)
    assert loose.unavailable == () and loose.matched == (("ask_user_input_v0", "ask_user"),)


def test_equivalents_only_ever_add_grants():
    for name in ("copilot-cli", "vscode-copilot", "claude-code", "claude-ai"):
        tools = sorted(load_profile(name).tools)
        exact = set(bind_grants(PACK, tools, equivalents=False).granted)
        loose = set(bind_grants(PACK, tools).granted)
        assert exact <= loose


def test_copilot_cli_profile_has_web_search():
    assert "web_search" in load_profile("copilot-cli").tools


# --- the compiler and the CLI ---------------------------------------------------------------

SKILL = ("---\nname: book\ndescription: Book a table.\n---\n# Book\n\n"
         "Call `ask_user_input_v0` to ask which evening suits, then use `web_search`.\n")


def test_profile_grants_another_name_of_its_tool_unless_exact():
    from dataclasses import replace
    code = load_profile("claude-code")
    assert code.grants("ask_user_input_v0") and code.grants("web_search")
    assert not replace(code, exact=True).grants("ask_user_input_v0")
    assert not code.grants("slack_send_message")


def test_compiler_declares_equivalents_with_their_provenance():
    from skillc.checker import check
    from skillc.frontend.markdown import compile_markdown
    res = compile_markdown(SKILL, load_profile("claude-code"))
    assert res.declared["ask_user_input_v0"] == "profile:claude-code(same tool as askuserquestion)"
    assert check(res.pack).achievable


def test_cli_counts_equivalents_and_can_require_exact_names(tmp_path, capsys):
    from skillc.cli import main
    path = tmp_path / "SKILL.md"
    path.write_text(SKILL, encoding="utf-8")
    assert main(["check", str(path), "--profile", "claude-code"]) == 0
    assert main(["check", str(path), "--profile", "claude-code", "--exact-tool-names"]) == 1
    assert "ask_user_input_v0" in capsys.readouterr().out
    assert main(["check", str(path), "--profile", "vscode-copilot"]) == 1   # no web search


def test_environment_need_finds_the_tool_under_another_name():
    from skillc.env.facts import need
    from skillc.env.model import Environment
    env = Environment()
    p = env.add_node("principal/agent", "principal", "agent")
    env.add_node("/", "scope", "session", level="root")
    env.add_node("tool/ask_user", "tool", "ask_user")
    env.add_edge(p, env.add_node("allow", "role", "allow", actions=["ask_user"]),
                 "assigned", scope="/")
    fact = need(env, {"tool": "AskUserQuestion"})
    assert fact.value is True and "AskUserQuestion is ask_user here" in fact.reasons[0]
    assert need(env, {"tool": "slack_send_message"}).value is False
