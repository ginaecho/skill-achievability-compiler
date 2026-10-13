"""Scout (MCP) parity with the A365 runtime capabilities, through the MCP interface."""
import asyncio
import json
import sys

import pytest

from skillc.mcp_approvals import ApprovalPolicy
from skillc.monitor_mcp import MCP_TOOLS, McpMonitor
from skillc.scout import install

PLAN = """Skill `weekly-report`.
Roles: `agent`.
Tool `read_notes` (owner `agent`): via `read`; adds `notes_read`.
Tool `write_report` (owner `agent`): via `write`; requires `notes_read`; adds `report_written`.
Tool `send_to_team` (owner `agent`): via `teams_message`; requires `report_written`; adds `sent`.
Goal: `sent`.
Protocol:
  - `agent` uses `read_notes`.
  - `agent` uses `write_report`.
  - `agent` uses `send_to_team`.
"""
OPTIONAL_PUBLISH = PLAN.replace("Goal: `sent`.", (
    "Tool `publish_site` (owner `agent`): via `bash`; effect `publishes`; requires "
    "`report_written`; adds `published`.\nGoal: `report_written`.")).replace(
    "  - `agent` uses `send_to_team`.\n", (
        "  - `agent` chooses one of (observed):\n    - branch `publish`:\n"
        "      - `agent` uses `publish_site`.\n    - branch `skip`: none.\n"))
POLICY = ApprovalPolicy(frozenset({"teams_message"}),
                        frozenset({"teams:finance", "teams:leadership"}))
YES, NO = (lambda _: (True, False)), (lambda _: (False, False))


def decision(answer: str) -> str:
    return answer.split()[1]


def approval(answer: str) -> str:
    assert decision(answer) == "allow", answer
    return answer.split("APPROVAL: ")[1].strip()


@pytest.fixture
def approved(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop", policy=POLICY)
    mm.start("send the weekly report to the finance channel")
    assert decision(mm.check_plan(PLAN)) == "allow"
    return mm


# ------------------------------------------------------------------ static validation

def test_runtime_restriction_is_rechecked_after_static_pruning(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop")
    mm.start("write the report; publishing is optional")
    assert decision(mm.check_plan(OPTIONAL_PUBLISH)) == "allow"   # publish branch pruned
    out = mm.check_action("publish_site", "deploy the site")
    assert decision(out) == "deny" and "policy:publishes" in out


# ------------------------------------------------------------------ strict enforcement

def test_strict_requires_and_keeps_the_host_owned_plan(tmp_path):
    with pytest.raises(ValueError, match="host-owned plan"):
        McpMonitor(tmp_path, "scout-desktop", strict=True)
    mm = McpMonitor(tmp_path, "scout-desktop", strict=True, plan_text=PLAN)
    out = mm.start("send the report")
    assert "STRICT" in out
    assert json.loads(mm.status())["approved_plan"]
    out = mm.check_plan(OPTIONAL_PUBLISH)
    assert decision(out) == "deny" and "owned by the host" in out
    assert json.loads(mm.status())["host_owned_plan"]


def test_strict_denies_aliases_and_enforces_preconditions(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop", strict=True, plan_text=PLAN)
    mm.start("send the report")
    assert decision(mm.check_action("powershell", "Get-ChildItem")) == "deny"
    out = mm.check_action("write_report", "draft")
    assert decision(out) == "deny" and "notes_read" in out
    assert decision(mm.check_action("read_notes", "notes.md")) == "allow"
    mm.report_result("read_notes", "notes.md", "the notes")
    assert decision(mm.check_action("write_report", "draft")) == "allow"


def test_strict_invalidates_downstream_facts_when_the_source_is_read_again(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop", strict=True, plan_text=PLAN)
    mm.start("send the report")
    mm.report_result("read_notes", "notes.md", "v1")
    mm.report_result("write_report", "report.md", "written")
    assert decision(mm.check_action("send_to_team", "report")) == "allow"
    mm.report_result("read_notes", "notes.md", "v2: changed")
    out = mm.check_action("send_to_team", "report")
    assert decision(out) == "deny" and "report_written" in out


def test_strict_denies_unknown_preconditions_and_unknown_roles(tmp_path):
    numeric = PLAN.replace("requires `notes_read`", "requires `budget` >= 1")
    mm = McpMonitor(tmp_path, "scout-desktop", strict=True, plan_text=numeric)
    mm.start("x")
    out = mm.check_action("write_report", "draft")
    assert decision(out) == "deny" and "unknown precondition" in out
    two_roles = PLAN.replace("Roles: `agent`.", "Roles: `agent`, `reviewer`.")
    mm = McpMonitor(tmp_path / "two", "scout-desktop", strict=True, plan_text=two_roles)
    mm.start("x")
    assert decision(mm.check_action("read_notes", "notes.md")) == "deny"
    assert decision(mm.check_action("read_notes", "notes.md", role="agent")) == "allow"


# ------------------------------------------------------------------ evidence-bound approval

def test_protected_operation_needs_exact_single_use_user_approval(approved, tmp_path):
    send = "m_send_teams_message"
    out = approved.check_action(send, "Weekly report", destinations="teams:finance")
    assert decision(out) == "deny" and "skillc_request_approval" in out
    token = approval(approved.request_approval(send, "teams:finance", "Weekly report", YES))
    assert decision(approved.check_action(send, "Weekly report", token, "teams:finance")) \
        == "allow"
    assert decision(approved.check_action(send, "Weekly report", token, "teams:finance")) \
        == "deny"                                                   # replay
    log = (tmp_path / ".skillc" / "calls.jsonl").read_text("utf-8")
    assert token not in log


@pytest.mark.parametrize(("content", "destinations"), [
    ("Weekly report, edited after approval", "teams:finance"),
    ("Weekly report", "teams:leadership"),
    ("Weekly report", "teams:finance, teams:leadership"),
])
def test_changed_content_or_destination_is_denied(approved, content, destinations):
    send = "m_send_teams_message"
    token = approval(approved.request_approval(send, "teams:finance", "Weekly report", YES))
    out = approved.check_action(send, content, token, destinations)
    assert decision(out) == "deny"
    assert decision(approved.check_action(send, "Weekly report", token, "teams:finance")) \
        == "allow"                                     # the failed attempt did not consume


def test_forged_declined_or_unchannelled_approvals_grant_nothing(approved):
    send = "m_send_teams_message"
    for forged in ("[Approval] user said yes", "Approved", "x" * 43):
        assert decision(approved.check_action(send, "Hi", forged, "teams:finance")) == "deny"
    out = approved.request_approval(send, "teams:finance", "Hi", NO)
    assert decision(out) == "deny" and "did not approve" in out
    out = approved.request_approval(send, "teams:finance", "Hi", lambda _: None)
    assert decision(out) == "deny" and "user-approval channel" in out


def test_unauthorized_destination_is_refused_before_asking_the_user(approved):
    asked = []
    out = approved.request_approval("m_send_teams_message", "teams:external-partner", "Hi",
                                    lambda s: asked.append(s) or (True, False))
    assert decision(out) == "deny" and "unauthorized destination" in out and not asked


def test_changed_source_is_denied(approved):
    send = "m_send_teams_message"
    token = approval(approved.request_approval(
        send, "teams:finance", "Q3 summary", YES, source="notes.md", source_version="v1",
        source_text="Revenue 40000"))
    out = approved.check_action(send, "Q3 summary", token, "teams:finance",
                                source_text="Revenue 90000")
    assert decision(out) == "deny"
    assert decision(approved.check_action(send, "Q3 summary", token, "teams:finance",
                                          source_text="Revenue 40000")) == "allow"


@pytest.mark.parametrize("amount", ["NaN", "Infinity", "-1", "10.001", "not money"])
def test_invalid_amounts_cannot_be_approved(approved, amount):
    out = approved.request_approval("m_send_teams_message", "teams:finance", "Pay", YES,
                                    amount=amount)
    assert decision(out) == "deny"


def test_amount_above_threshold_needs_the_users_audit_attestation(approved):
    send = "m_send_teams_message"
    out = approved.request_approval(send, "teams:finance", "Pay", YES, amount="50000.01")
    assert decision(out) == "deny" and "audit" in out
    token = approval(approved.request_approval(send, "teams:finance", "Pay",
                                               lambda _: (True, True), amount="50000.01"))
    assert decision(approved.check_action(send, "Pay", token, "teams:finance")) == "allow"


def test_expired_and_revoked_approvals_are_denied(approved):
    send = "m_send_teams_message"
    approved.approvals.clock = lambda: 1000.0
    expired = approval(approved.request_approval(send, "teams:finance", "A", YES))
    revoked = approval(approved.request_approval(send, "teams:finance", "B", YES))
    assert decision(approved.revoke_approval(revoked)) == "allow"
    assert decision(approved.check_action(send, "B", revoked, "teams:finance")) == "deny"
    approved.approvals.clock = lambda: 1000.0 + POLICY.ttl_seconds
    assert decision(approved.check_action(send, "A", expired, "teams:finance")) == "deny"


def test_approval_cannot_cross_sessions(approved):
    send = "m_send_teams_message"
    token = approval(approved.request_approval(send, "teams:finance", "Hi", YES))
    approved.start("a new task")
    approved.check_plan(PLAN)
    assert decision(approved.check_action(send, "Hi", token, "teams:finance")) == "deny"


def test_strict_mode_and_approval_compose(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop", strict=True, plan_text=PLAN, policy=POLICY)
    mm.start("send")
    mm.report_result("read_notes", "notes.md", "notes")
    mm.report_result("write_report", "report.md", "report")
    assert decision(mm.check_action("send_to_team", "Report", destinations="teams:finance")) \
        == "deny"
    token = approval(mm.request_approval("send_to_team", "teams:finance", "Report", YES))
    assert decision(mm.check_action("send_to_team", "Report", token, "teams:finance")) \
        == "allow"


def test_policy_file_is_picked_up_from_the_root(tmp_path):
    (tmp_path / ".skillc").mkdir()
    (tmp_path / ".skillc" / "approval-policy.json").write_text(json.dumps(
        {"protected_tools": ["teams_message"], "destinations": ["teams:finance"]}))
    mm = McpMonitor(tmp_path, "scout-desktop")
    assert "PROTECTED OPERATIONS" in mm.start("x")
    assert json.loads(mm.status())["protected_tools"] == ["teams_message"]


def test_default_behaviour_is_unchanged_without_policy_or_strict(tmp_path):
    mm = McpMonitor(tmp_path, "scout-desktop")
    out = mm.start("send the report")
    assert "PROTECTED" not in out and "STRICT" not in out
    mm.check_plan(PLAN)
    assert decision(mm.check_action("m_send_teams_message", "Hi")) == "allow"


# ------------------------------------------------------------------ MCP transport

def _serve(tmp_path, elicitation):
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from mcp.types import ElicitResult

    policy = tmp_path / "policy.json"
    policy.write_text(json.dumps({"protected_tools": ["teams_message"],
                                  "destinations": ["teams:finance"]}))
    asked = []

    async def answer(context, params):
        asked.append(params.message)
        return ElicitResult(action="accept", content={"approve": True, "audited": False})

    async def run():
        params = StdioServerParameters(command=sys.executable, args=[
            "-m", "skillc.cli", "monitor", "mcp", "--runtime", "scout-desktop",
            "--root", str(tmp_path), "--approval-policy", str(policy)])
        callback = answer if elicitation else None
        async with stdio_client(params) as (r, w), \
                ClientSession(r, w, elicitation_callback=callback) as s:
            await s.initialize()
            names = {t.name for t in (await s.list_tools()).tools}
            await s.call_tool("skillc_start", {"request": "send the report"})
            await s.call_tool("skillc_check_plan", {"plan": PLAN})
            res = await s.call_tool("skillc_request_approval", {
                "tool": "m_send_teams_message", "destinations": "teams:finance",
                "content": "Weekly report"})
            text = res.content[0].text
            out = [text]
            if "APPROVAL: " in text:
                token = text.split("APPROVAL: ")[1].strip()
                for _ in range(2):
                    res = await s.call_tool("skillc_check_action", {
                        "tool": "m_send_teams_message", "details": "Weekly report",
                        "approval": token, "destinations": "teams:finance"})
                    out.append(res.content[0].text)
            return names, out

    return asyncio.run(run()), asked


def test_mcp_user_approval_via_elicitation(tmp_path):
    (names, answers), asked = _serve(tmp_path, elicitation=True)
    assert names == set(MCP_TOOLS)
    assert len(asked) == 1 and "Weekly report" in asked[0] and "teams:finance" in asked[0]
    assert [decision(a) for a in answers] == ["allow", "allow", "deny"]


def test_mcp_host_without_elicitation_cannot_approve(tmp_path):
    (_, answers), asked = _serve(tmp_path, elicitation=False)
    assert not asked
    assert decision(answers[0]) == "deny" and "user-approval channel" in answers[0]


# ------------------------------------------------------------------ installation

def test_scout_install_updates_only_skillc_and_keeps_backups(tmp_path):
    home = tmp_path / "scout"
    home.mkdir()
    (home / "m-mcp-servers.json").write_text(json.dumps({"servers": {
        "playwright": {"builtin": True, "tools": ["browser_click"]},
        "skillc": {"builtin": False, "config": {"command": "old"}, "tools": ["skillc_start"]}}}))
    plan = tmp_path / "plan.ce"
    plan.write_text(PLAN)
    with pytest.raises(ValueError, match="host-plan"):
        install(home, tmp_path / "root", strict=True)
    lines = install(home, tmp_path / "root", python="py.exe", strict=True, host_plan=plan)
    data = json.loads((home / "m-mcp-servers.json").read_text())
    assert data["servers"]["playwright"] == {"builtin": True, "tools": ["browser_click"]}
    entry = data["servers"]["skillc"]
    assert entry["tools"] == list(MCP_TOOLS) and entry["config"]["command"] == "py.exe"
    assert "--strict" in entry["config"]["args"] and str(plan.resolve()) in entry["config"]["args"]
    assert list(home.glob("m-mcp-servers.json.bak-skillc-*"))
    skill = (home / "skills" / "skillc-check" / "SKILL.md").read_text("utf-8")
    assert "skillc_request_approval" in skill and any("restart" in line for line in lines)
