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


def test_binding_matches_exact_names_unless_equivalents_are_asked_for():
    copilot = sorted(load_profile("copilot-cli").tools)
    exact = bind_grants(PACK, copilot)
    assert exact.unavailable == ("ask_user_input_v0",) and exact.matched == ()
    loose = bind_environment(PACK, copilot, equivalents=True)
    assert loose.unavailable == () and loose.matched == (("ask_user_input_v0", "ask_user"),)


def test_equivalents_only_ever_add_grants():
    for name in ("copilot-cli", "vscode-copilot", "claude-code", "claude-ai"):
        tools = sorted(load_profile(name).tools)
        exact = set(bind_grants(PACK, tools).granted)
        loose = set(bind_grants(PACK, tools, equivalents=True).granted)
        assert exact <= loose


def test_copilot_cli_profile_has_web_search():
    assert "web_search" in load_profile("copilot-cli").tools
