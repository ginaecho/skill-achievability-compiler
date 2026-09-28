"""Runtime monitor (skillc.monitor): plan gate, reasoning, actions, observations, and the
Claude Code hook protocol."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

from skillc.monitor import ALLOW, DENY, WARN, Config, Monitor, Rule, thinking_since

GOOD = """Skill `fix-tests`.
Roles: `agent`.
Tool `run_tests` (owner `agent`): via `bash`; adds `tests_run`.
Tool `edit_code` (owner `agent`): via `edit`; requires `tests_run`; adds `fixed`.
Goal: `fixed`.
Protocol:
  - `agent` uses `run_tests`.
  - `agent` uses `edit_code`.
"""

DEPLOY = GOOD.replace(
    "Goal: `fixed`.",
    "Tool `deploy` (owner `agent`): via `bash`; needs `vercel_account`; requires `fixed`; "
    "adds `deployed`.\nGoal: `fixed` and `deployed`.").replace(
    "  - `agent` uses `edit_code`.\n", "  - `agent` uses `edit_code`.\n  - `agent` uses `deploy`.\n")

OPTIONAL_DEPLOY = GOOD.replace(
    "Goal: `fixed`.",
    "Tool `deploy` (owner `agent`): via `bash`; needs `vercel_account`; requires `fixed`; "
    "adds `deployed`.\nGoal: `fixed`.") + (
    "  - `agent` chooses one of (observed):\n"
    "    - branch `ship`:\n      - `agent` uses `deploy`.\n"
    "    - branch `skip`: none.\n")

PANDOC = GOOD.replace("via `edit`; requires", "via `bash`; runs `pandoc`; requires")


def mon(tmp_path, **kw) -> Monitor:
    return Monitor(Config(**kw), tmp_path)


def test_only_achievable_plan_is_approved(tmp_path):
    m = mon(tmp_path)
    assert m.submit_plan(DEPLOY).action == DENY          # needs an account the runtime lacks
    assert m.state.plan is None
    d = m.submit_plan(OPTIONAL_DEPLOY)                    # deploy is skippable -> achievable
    assert d.action == ALLOW and m.state.plan == OPTIONAL_DEPLOY


def test_refusal_names_the_witness(tmp_path):
    d = mon(tmp_path).submit_plan(DEPLOY)
    assert "deploy" in d.witness and "vercel_account" in d.reason


def test_unparsable_plan_is_denied_with_location(tmp_path):
    d = mon(tmp_path).submit_plan("Skill `x`.\nTool deploy.\n")
    assert d.action == DENY and "does not parse" in d.reason


def test_implementation_is_gated_on_an_approved_plan(tmp_path):
    m = mon(tmp_path)
    assert m.pre_action("Read", {"file_path": "a.py"}).action == ALLOW    # looking is free
    assert m.pre_action("Bash", {"command": "pytest"}).action == DENY     # no plan yet
    m.submit_plan(GOOD)
    assert m.pre_action("Bash", {"command": "pytest -q"}).action == ALLOW
    assert m.pre_action("Edit", {"file_path": "a.py", "new_string": "x"}).action == ALLOW
    # plan conformance: the plan binds no Tool via `write`
    assert m.pre_action("Write", {"file_path": "b.py", "content": "x"}).action == DENY


def test_writing_the_plan_file_is_the_submission(tmp_path):
    m = mon(tmp_path)
    plan = str(tmp_path / ".skillc" / "plan.ce")
    assert m.pre_action("Write", {"file_path": plan, "content": DEPLOY}).action == DENY
    assert m.pre_action("Write", {"file_path": plan, "content": GOOD}).action == ALLOW
    assert m.state.plan == GOOD
    assert m.pre_action("Edit", {"file_path": plan, "new_string": "x"}).action == DENY


def test_action_needing_what_the_runtime_lacks_is_blocked(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    d = m.pre_action("Bash", {"command": "aws s3 cp out.csv s3://bucket/"})
    assert d.action == DENY and "aws_account" in d.reason


def test_runtime_policy_forbids_external_writes(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    d = m.pre_action("Bash", {"command": "git push origin main"})
    assert d.action == DENY and "writes_external" in d.reason


def test_runtime_without_a_tool_blocks_it(tmp_path):
    m = mon(tmp_path, runtime="office-assistant", require_plan=False)
    assert m.pre_action("Bash", {"command": "ls"}).action == DENY


def test_reasoning_towards_the_impossible_stops_actions(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    d = m.observe_thinking("Tests pass. Now I'll run `eas build` to ship the app.")
    assert d.action == DENY and "expo_account" in d.reason
    assert m.pre_action("Bash", {"command": "pytest"}).action == DENY     # held
    assert m.submit_plan(GOOD).action == ALLOW                            # re-plan clears it
    assert m.pre_action("Bash", {"command": "pytest"}).action == ALLOW


def test_negated_reasoning_does_not_stop(tmp_path):
    m = mon(tmp_path)
    assert m.observe_thinking("I can't use eas build here, so I stay local.").action == ALLOW


def test_thinking_warn_mode_does_not_block(tmp_path):
    m = mon(tmp_path, thinking="warn")
    m.submit_plan(GOOD)
    assert m.observe_thinking("Next: eas build for production.").action == WARN
    assert m.pre_action("Bash", {"command": "pytest"}).action == ALLOW


def test_prohibited_behaviour_rules(tmp_path):
    rule = Rule(id="no-prod-db", description="never touch the production database",
                pattern=r"prod(uction)?[-_ ]?db")
    effect = Rule(id="no-publish", description="publishing is prohibited", effect="publishes")
    m = mon(tmp_path, prohibited=[rule, effect])
    assert m.observe_thinking("I will migrate prod-db directly.").action == DENY
    pub = GOOD.replace("via `edit`;", "via `edit`; effect `publishes`;")
    assert m.submit_plan(pub).action == DENY
    m.state.block = None
    m.submit_plan(GOOD)
    assert m.pre_action("Bash", {"command": "psql $PROD_DB_URL"}).action == DENY


def test_observed_missing_program_revokes_the_plan(tmp_path):
    m = mon(tmp_path)
    assert m.submit_plan(PANDOC).action == ALLOW          # installable in developer-sandbox
    m.state.missing_programs = []
    d = m.post_action("Bash", {"command": "pandoc a.md -o a.docx"},
                      "bash: pandoc: command not found")
    assert d.action == DENY and "pandoc" in d.reason and m.state.plan is None
    assert m.pre_action("Bash", {"command": "pytest"}).action == DENY


def test_observed_rejected_credential(tmp_path):
    m = mon(tmp_path, runtime="developer-sandbox")
    m.submit_plan(GOOD)
    d = m.post_action("Bash", {"command": "aws s3 ls"}, "An error occurred: 403 Forbidden")
    assert "aws_account" in m.state.missing_resources
    assert d.action == WARN                                # GOOD does not need it


def test_state_persists_across_processes(tmp_path):
    m = mon(tmp_path)
    m.submit_plan(GOOD)
    m.save()
    assert mon(tmp_path).state.plan == GOOD


def test_transcript_reader(tmp_path):
    t = tmp_path / "t.jsonl"
    rows = [{"message": {"role": "user", "content": "hi"}},
            {"message": {"role": "assistant", "content": [
                {"type": "thinking", "thinking": "plan: eas build"},
                {"type": "tool_use", "name": "Bash", "input": {}}]}}]
    t.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    text, off = thinking_since(t, 0)
    assert "eas build" in text and off == t.stat().st_size
    assert thinking_since(t, off) == ("", off)


def _hook(kind, event, cwd):
    p = subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "hook", kind],
                       input=json.dumps(event), capture_output=True, text=True, cwd=cwd)
    assert p.returncode == 0, p.stderr
    return json.loads(p.stdout) if p.stdout.strip() else None


def test_claude_code_hook_protocol_end_to_end(tmp_path):
    subprocess.run([sys.executable, "-m", "skillc.cli", "monitor", "init", "--root",
                    str(tmp_path)], check=True, capture_output=True)
    ev = {"session_id": "s1", "cwd": str(tmp_path)}
    out = _hook("prompt", {**ev, "prompt": "deploy it with eas build"}, tmp_path)
    ctx = out["hookSpecificOutput"]["additionalContext"]
    assert "SKILLC RUNTIME MONITOR" in ctx and "expo_account" in ctx
    out = _hook("pre", {**ev, "tool_name": "Bash", "tool_input": {"command": "pytest"}}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    plan = str(tmp_path / ".skillc" / "plan.ce")
    out = _hook("pre", {**ev, "tool_name": "Write",
                        "tool_input": {"file_path": plan, "content": GOOD}}, tmp_path)
    assert "ACHIEVABLE" in out["hookSpecificOutput"]["additionalContext"]
    assert _hook("pre", {**ev, "tool_name": "Bash", "tool_input": {"command": "pytest"}},
                 tmp_path) is None                                  # allowed silently
    t = tmp_path / "t.jsonl"
    t.write_text(json.dumps({"message": {"role": "assistant", "content": [
        {"type": "thinking", "thinking": "All green; now `npm publish` the package."}]}}) + "\n")
    out = _hook("pre", {**ev, "transcript_path": str(t), "tool_name": "Bash",
                        "tool_input": {"command": "ls"}}, tmp_path)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "writes_external" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_inactive_without_config(tmp_path):
    assert _hook("pre", {"cwd": str(tmp_path), "tool_name": "Bash",
                         "tool_input": {"command": "rm -rf x"}}, tmp_path) is None
