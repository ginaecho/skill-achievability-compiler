"""Compile-and-check the compiler against REAL, public agent skills.

By default this looks for a checkout/mount of Anthropic's public skills
repository (https://github.com/anthropics/skills) at /mnt/skills or at
$SKILLC_SKILLS_DIR.  Fetch a copy with scripts/fetch_skills.py if needed.
The whole module is skipped when no corpus is available, so CI without the
corpus still passes.
"""
import os
from pathlib import Path

import pytest

from skillc import check, compile_file, load_profile

SKILLS_DIR = Path(os.environ.get("SKILLC_SKILLS_DIR", "/mnt/skills"))

pytestmark = pytest.mark.skipif(
    not SKILLS_DIR.is_dir() or not list(SKILLS_DIR.rglob("SKILL.md")),
    reason=f"no real-skill corpus at {SKILLS_DIR} (set SKILLC_SKILLS_DIR)")


def all_skill_files() -> list[Path]:
    return sorted(SKILLS_DIR.rglob("SKILL.md"))


def _id(p: Path) -> str:
    return str(p.relative_to(SKILLS_DIR).parent)


CLAUDE_AI = load_profile("claude-ai")
CLAUDE_CODE = load_profile("claude-code")


@pytest.mark.parametrize("path", all_skill_files(), ids=_id)
def test_every_real_skill_compiles_to_a_valid_pack(path):
    res = compile_file(path, CLAUDE_AI)
    assert res.pack["name"]
    assert isinstance(res.pack["capabilities"], dict)
    # the pack passed validate_pack inside compile_file; checking must not crash
    v = check(res.pack)
    assert v.label in ("ACHIEVABLE", "IMPOSSIBLE")


# Skills whose own frontmatter makes them conditional on an external MCP
# connector (a browser extension, a linked desktop) that the bare claude-ai
# profile does not grant.  A refutation here is the checker working, not a
# false alarm: the document really does instruct the agent to call a tool the
# profile does not provide, so the pair below asserts the refutation *and* the
# capability it must name.  Everything else in the corpus must be achievable.
CONNECTOR_DEPENDENT = {
    "examples/chrome-browser": "tabs_context_mcp",
    "examples/computer-use": "computer_request_access",
}


@pytest.mark.parametrize("path", all_skill_files(), ids=_id)
def test_real_skills_achievable_in_their_home_runtime(path):
    """Every skill shipped for the consumer runtime must be achievable under
    the claude-ai profile: these skills are real and deployed, so a refutation
    here would be a false alarm (a soundness bug in the front-end mapping).
    The exception is a skill that declares a connector requirement of its own;
    those are checked by ``test_connector_dependent_skills_name_the_connector``
    below, which is the stronger assertion."""
    if _id(path) in CONNECTOR_DEPENDENT:
        pytest.skip("connector-dependent: see test_connector_dependent_skills")
    v = check(compile_file(path, CLAUDE_AI).pack)
    assert v.achievable, (
        f"{path}: false refutation {v.reason} {v.frontier} -- "
        f"deployed skill judged impossible in its home runtime")


@pytest.mark.parametrize("skill,cap", sorted(CONNECTOR_DEPENDENT.items()))
def test_connector_dependent_skills_name_the_connector(skill, cap):
    """A skill that needs a connector the profile lacks must be refuted with
    that connector's tool named, and must become achievable once it is
    granted -- the checker localises the missing grant instead of merely
    saying no."""
    path = SKILLS_DIR / skill / "SKILL.md"
    if not path.exists():
        pytest.skip(f"{skill} not in corpus")
    v = check(compile_file(path, CLAUDE_AI).pack)
    assert not v.achievable, f"{skill}: expected a refutation under claude-ai"
    assert v.reason == "MISSING_CAPABILITY"
    assert cap in v.frontier, f"{skill}: {cap} not named in {v.frontier}"
    widened = CLAUDE_AI.with_tools(list(v.frontier))
    assert check(compile_file(path, widened).pack).achievable, (
        f"{skill}: still refuted after granting {v.frontier}")


def test_consumer_only_skills_are_refuted_under_claude_code():
    """Skills built around consumer-app tools must be refuted under the
    claude-code profile, with the missing tool named in the frontier."""
    path = SKILLS_DIR / "examples/call-to-book/SKILL.md"
    if not path.exists():
        pytest.skip("call-to-book not in corpus")
    v = check(compile_file(path, CLAUDE_CODE).pack)
    assert not v.achievable
    assert v.reason == "MISSING_CAPABILITY"
    assert "ask_user_input_v0" in v.frontier


def test_profile_narrowing_refutes_with_the_removed_tool_named():
    """Mutation testing on real skills, refutation direction: take a skill
    that is achievable under claude-ai and remove one agent-tool it actually
    invokes -- the compiler must flip to IMPOSSIBLE and name that tool."""
    from skillc.profiles import Profile
    mutated = 0
    for path in all_skill_files():
        res = compile_file(path, CLAUDE_AI)
        if res.embedded:
            continue
        used = {i.tool for i in res.invocations if i.kind == "agent-tool"}
        if not used or not check(res.pack).achievable:
            continue
        victim = sorted(used)[0]
        narrowed = Profile(name="narrowed", tools=CLAUDE_AI.tools - {victim},
                           shell=CLAUDE_AI.shell)
        v = check(compile_file(path, narrowed).pack)
        assert not v.achievable, f"{path}: still achievable without {victim}"
        assert v.reason == "MISSING_CAPABILITY"
        assert victim in v.frontier, f"{path}: {victim} not named in frontier"
        mutated += 1
    assert mutated > 0, "no skill exercised the narrowing mutation"


def test_profile_widening_is_monotone_on_real_skills():
    """T3 on real data: granting the missing tools flips IMPOSSIBLE ->
    ACHIEVABLE, and never the other way."""
    for path in all_skill_files():
        v_code = check(compile_file(path, CLAUDE_CODE).pack)
        if v_code.achievable or v_code.reason != "MISSING_CAPABILITY":
            continue
        widened = CLAUDE_CODE.with_tools(list(v_code.frontier))
        v_wide = check(compile_file(path, widened).pack)
        assert v_wide.achievable, (
            f"{path}: still {v_wide.reason} after granting {v_code.frontier}")
