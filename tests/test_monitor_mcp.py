"""The runtime monitor as MCP tools (skillc.monitor_mcp), for hosts without hooks."""
import asyncio
import json
import sys

import pytest

from skillc.monitor_mcp import McpMonitor

GOOD = """Skill `fix-tests`.
Roles: `agent`.
Tool `run_tests` (owner `agent`): via `bash`; adds `tests_run`.
Tool `edit_code` (owner `agent`): via `edit`; requires `tests_run`; adds `fixed`.
Goal: `fixed`.
Protocol:
  - `agent` uses `run_tests`.
  - `agent` uses `edit_code`.
"""
S3 = GOOD.replace("Goal: `fixed`.",
                  "Tool `upload` (owner `agent`): via `bash`; needs `aws_account`; requires "
                  "`fixed`; adds `uploaded`.\nGoal: `fixed` and `uploaded`.").replace(
    "  - `agent` uses `edit_code`.\n", "  - `agent` uses `edit_code`.\n  - `agent` uses `upload`.\n")


def test_stop_explain_replan_through_tools(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop")
    out = mm.start("fix the tests, then copy the report to S3 with aws s3 cp")
    assert "skillc_check_plan" in out and "`scout-desktop`" in out
    assert "intent check" in out and "aws_account" in out

    out = mm.check_action("PowerShell", "pytest")
    assert out.startswith("DECISION: deny") and "no approved plan" in out

    out = mm.check_plan(S3)
    assert out.startswith("DECISION: deny   NEXT: ask_user   USER_NEEDS: aws_account")
    assert "Only the user can provide `aws_account`" in out

    assert mm.check_plan(GOOD).startswith("DECISION: allow")
    assert mm.check_action("powershell", "pytest -q").startswith("DECISION: allow")

    out = mm.check_reasoning("Tests pass. Now I'll run aws s3 cp report.csv s3://bucket/.")
    assert out.startswith("DECISION: warn   NEXT: ask_user") and "skillc question" in out
    assert mm.check_action("edit", "fix the assertion").startswith("DECISION: allow")

    out = mm.report_result("powershell", "pandoc a.md -o a.docx",
                           "pandoc : The term 'pandoc' is not recognized as the name of a "
                           "cmdlet, function, script file, or operable program.")
    assert out.startswith("DECISION: warn")              # observed; GOOD does not run pandoc
    assert "program `pandoc` is missing" in out and "still ACHIEVABLE" in out
    status = json.loads(mm.status())
    assert status["approved_plan"] and "pandoc" in status["missing_programs"]

    calls = [json.loads(x) for x in
             (tmp_path / ".skillc" / "calls.jsonl").read_text("utf-8").splitlines()]
    assert [c["call"] for c in calls][:3] == ["start", "check_action", "check_plan"]
    assert len({c["session"] for c in calls}) == 1


def test_start_begins_a_fresh_session(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop")
    mm.start("fix the tests")
    mm.check_plan(GOOD)
    mm.start("another task")
    assert json.loads(mm.status())["approved_plan"] is False


def test_apply_patch_stands_for_write_or_edit(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop")
    mm.start("create a file")
    write_plan = GOOD.replace("via `edit`", "via `write`")
    mm.check_plan(write_plan)
    assert mm.check_action("apply_patch", "create notes.md").startswith("DECISION: allow")
    mm.check_plan(GOOD)                                   # edits: `apply_patch` is `edit`
    assert mm.check_action("apply_patch", "fix a.py").startswith("DECISION: allow")


def test_unknown_tool_is_named(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop")
    mm.start("x")
    mm.check_plan(GOOD)
    out = mm.check_action("xcodebuild_tool", "build")
    assert out.startswith("DECISION: deny") and "not a tool of runtime" in out


# The request Microsoft Scout passed to skillc_start, and the plan it then submitted: the
# WorkIQ read was hidden in the generated script, so the plan alone looked local.
SCOUT_REQUEST = ("create me a pipeline that I can summarize my colleagues latest discussions "
                 "into an excel sheet")
NARROWED = "summarize the discussions I take part in with my colleagues into an excel sheet"
SCOUT_PLAN = """Skill `discussion-summary-pipeline`.
Roles: `agent`, `user`.
Tool `create_pipeline_files` (owner `agent`): via `write`; needs `local_filesystem`; adds `pipeline_files_created`; effect `local`.
Tool `validate_pipeline` (owner `agent`): via `bash`; needs `shell`, `local_filesystem`; runs `python`, `openpyxl`; requires `pipeline_files_created`; adds `pipeline_validated`; effect `local`.
Initially true: none.
Goal: `pipeline_files_created` and `pipeline_validated`.
Protocol:
  - `agent` uses `create_pipeline_files`.
  - `agent` uses `validate_pipeline`.
"""


def test_other_peoples_m365_data_is_a_gap_and_gates_the_plan(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop")
    out = mm.start(SCOUT_REQUEST)
    assert "intent check" in out and "needs `others_m365_data`" in out
    assert "only what the signed-in user can already access" in out     # the note
    assert "discussions I take part in" in out                          # the substitute
    out = mm.check_plan(SCOUT_PLAN)
    assert out.startswith("DECISION: deny   NEXT: ask_user   USER_NEEDS: others_m365_data")
    assert "cannot provide" in out and "Narrower goal" in out and "skillc_start again" in out
    assert json.loads(mm.status())["approved_plan"] is False

    # the user accepts the narrower goal; the agent restarts with it in the user's words
    out = mm.start(NARROWED)
    assert "intent check" not in out
    assert mm.check_plan(SCOUT_PLAN).startswith("DECISION: allow")


def test_request_gate_follows_the_latest_prompt_in_hook_hosts(tmp_path):
    from skillc.monitor import ALLOW, ASK_USER, DENY, Config, Monitor
    m = Monitor(Config(runtime="scout-desktop"), tmp_path)
    assert "others_m365_data" in m.on_prompt(SCOUT_REQUEST, "s1")[1]
    d = m.submit_plan(SCOUT_PLAN)
    assert d.action == DENY and d.next == ASK_USER and d.user_needs == ["others_m365_data"]
    assert m.on_prompt("yes, only the discussions I'm in", "s1") == []
    assert m.submit_plan(SCOUT_PLAN).action == ALLOW


@pytest.mark.parametrize("text", [
    SCOUT_REQUEST,
    "summarize my colleagues' latest discussions",
    "colleagues discussions",
    "export my coworkers' emails to a sheet",
    "read my teammates' chats",
    "go through my colleagues' recent Teams messages",
    "summarize my team's conversations",
    "my manager's calendar for next week",
    "my reports' messages",
    "other people's mail",
    "search everyone's inbox",
    "someone else's mailbox",
    "my colleagues recent private chats",
    "read Sarah's inbox",
    "monitor my boss's mailbox",
    "access John's mailbox",
])
def test_others_m365_data_evidence_matches(text):
    from skillc.frontend.toolpolicy import load_library, match
    assert "others_m365_data" in {o.value for o in match(text, load_library())}


@pytest.mark.parametrize("text", [
    NARROWED,
    "summarize my emails",
    "summarize my discussions",
    "summarize discussions with my colleagues",
    "summarize the Teams channel I'm in",
    "email my colleagues the summary",
    "send my colleagues messages about the release",
    "summarize the discussions I took part in",
    "my colleagues' discussions that I'm part of",
    "my colleagues' chats with me",
    "check everyone's calendar availability",
    "read today's emails",
    "check the user's inbox",
    "invite my colleagues to a meeting",
])
def test_others_m365_data_evidence_ignores_own_and_shared_data(text):
    from skillc.frontend.toolpolicy import load_library, match
    assert "others_m365_data" not in {o.value for o in match(text, load_library())}


def test_served_over_stdio(tmp_path):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    async def run():
        params = StdioServerParameters(command=sys.executable, args=[
            "-m", "skillc.cli", "monitor", "mcp", "--runtime", "scout-desktop",
            "--root", str(tmp_path)])
        async with stdio_client(params) as (r, w), ClientSession(r, w) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
            await s.call_tool("skillc_start", {"request": "fix the tests"})
            res = await s.call_tool("skillc_check_plan", {"plan": S3})
            return names, res.content[0].text

    names, text = asyncio.run(run())
    assert names == {"skillc_start", "skillc_check_plan", "skillc_check_reasoning",
                     "skillc_check_action", "skillc_report_result", "skillc_status"}
    assert text.startswith("DECISION: deny   NEXT: ask_user")
