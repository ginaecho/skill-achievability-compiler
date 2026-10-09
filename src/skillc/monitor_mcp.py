"""MCP server adapter for the runtime monitor: skillc for hosts without hooks.

Some hosts (Microsoft Scout, for one) run the agent with no hook a plugin can attach to:
nothing runs before a tool call, and the agent's reasoning is not visible to plugins.
There the monitor is offered as tools the agent calls itself, as a skill instructs it:

  skillc_start(request)                  plan protocol + intent check; starts a session
  skillc_check_plan(plan)                submit a Controlled English plan
  skillc_check_reasoning(text)           the agent's own summary of what it intends
  skillc_check_action(tool, details)     an action before it is taken
  skillc_report_result(tool, details, output)   what the action showed
  skillc_status()                        the approved plan, held reason, observed facts

This is advisory: the agent decides whether to call the tools and whether to follow
them.  Every answer starts with one line the agent can act on,

  DECISION: allow|deny|warn   NEXT: replan|ask_user   USER_NEEDS: a, b

followed by what skillc found (docs/RUNTIME_MONITOR.md, "stop, explain, re-plan").

The state lives under `--root` (default ~/.skillc-mcp): `.skillc/monitor.json` (written
on first use), one state file per session, and `calls.jsonl`, a record of every call
and decision for evaluating a run afterwards.

  skillc monitor mcp --runtime scout-desktop [--root DIR]
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .frontend.prompts import CE_DOC, CE_RUNTIME_DOC, CE_SOFTWARE_DOC
from .frontend.runtime import runtime_note
from .monitor import ALLOW, Config, Decision, Monitor, state_lock

# tool names agents give their tools -> runtime tools (the scout-desktop vocabulary and
# the common ones of other runtimes); a runtime tool name maps to itself
MCP_TOOL_MAP = {"powershell": "bash", "shell": "bash", "bash": "bash", "terminal": "bash",
                "read": "read", "view": "read", "read_file": "read",
                "create": "write", "write": "write", "write_file": "write",
                "edit": "edit", "edit_file": "edit",
                "fetch": "web_fetch", "web_fetch": "web_fetch", "web_search": "web_search",
                "browser": "browser", "playwright": "browser",
                "workiq": "m365", "m365": "m365",
                "m_send_teams_message": "teams_message", "teams_message": "teams_message",
                "azure_devops": "azure_devops_mcp", "azure_devops_mcp": "azure_devops_mcp",
                "ask_user": "ask_user", "m_ask_user": "ask_user"}
# host tools that stand for more than one runtime tool: the first one the approved plan
# uses wins (Scout's `apply_patch` both creates and edits files)
MULTI_TOOLS = {"apply_patch": ("write", "edit")}
MCP_FREE_TOOLS = ("read", "view", "read_file", "grep", "glob", "web_search", "ask_user",
                  "m_ask_user", "m_recall")
PLAN_TOOL = "skillc_check_plan"
CONFIG = Path(".skillc") / "monitor.json"
CURRENT = Path(".skillc") / "current-session"


def mcp_config(runtime: str, thinking: str = "ask") -> Config:
    return Config(runtime=runtime, thinking=thinking, tool_map=dict(MCP_TOOL_MAP),
                  free_tools=MCP_FREE_TOOLS, plan_tools=(),
                  plan_file=".skillc/sessions/{session}/plan.ce",
                  state_file=".skillc/sessions/{session}/state.json")


def instructions(mon: Monitor) -> str:
    """The plan protocol for an agent that talks to skillc through tools."""
    return (
        "SKILLC is checking this task. skillc decides, without a model, whether a plan can "
        f"succeed in this runtime (`{mon.runtime.name}`). Before you act (run commands, "
        "write or edit files, send messages, change anything outside the conversation), "
        f"write your plan in SkillC Controlled English (CE) and submit it with {PLAN_TOOL}. "
        "One Tool per operation that changes the world or reaches beyond the conversation, "
        "bound with 'via' to the RUNTIME tool that performs it; 'needs' for any account, "
        "credential or paid service; 'runs' for specific software; 'effect' (local, "
        "reads_external, writes_external, publishes); optional work in a 'chooses one of "
        "(observed)' with a branch that skips it.\n"
        "Then, before each action, call skillc_check_action; after it, call "
        "skillc_report_result with what it printed. When your reasoning changes course, "
        "call skillc_check_reasoning with one or two sentences of what you now intend.\n"
        "Every answer starts with DECISION and NEXT. DECISION deny: do not take that step. "
        "NEXT replan: change the plan and submit it again. NEXT ask_user: only the user "
        "can fix this (USER_NEEDS lists what is missing); tell the user what skillc found "
        "and ask. DECISION warn: read the question and answer it for yourself before you "
        "go on.\n" + CE_DOC + CE_RUNTIME_DOC + CE_SOFTWARE_DOC + runtime_note(mon.runtime))


class McpMonitor:
    """One MCP server process: the monitor of the current session under `root`."""

    def __init__(self, root: Path, runtime: str, thinking: str = "ask"):
        self.root = Path(root)
        cfg_path = self.root / CONFIG
        if not cfg_path.exists():
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(json.dumps(mcp_config(runtime, thinking).dump(), indent=1)
                                + "\n", encoding="utf-8")
        self.config = Config.load(cfg_path)

    # ------------------------------------------------------------------ sessions
    def _session(self) -> str:
        p = self.root / CURRENT
        return p.read_text(encoding="utf-8").strip() if p.exists() else "default"

    def _new_session(self) -> str:
        sid = time.strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
        p = self.root / CURRENT
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(sid, encoding="utf-8")
        return sid

    def _run(self, call: str, args: dict, fn, sid: str | None = None) -> str:
        sid = sid or self._session()
        cfg = self.config.for_session(sid)
        with state_lock(self.root / cfg.state_file):
            mon = Monitor(self.config, self.root, session_id=sid)
            try:
                out = fn(mon)
            finally:
                mon.save()
        if isinstance(out, Decision):
            out = self._render(mon, out)
        with (self.root / ".skillc" / "calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "session": sid,
                                "call": call, "args": {k: str(v)[:2000] for k, v in
                                                       args.items()},
                                "answer": out[:4000]}) + "\n")
        return out

    def _render(self, mon: Monitor, d: Decision) -> str:
        head = f"DECISION: {d.action}"
        if d.next:
            head += f"   NEXT: {d.next}"
        if d.user_needs:
            head += "   USER_NEEDS: " + ", ".join(d.user_needs)
        reason = d.reason or ("skillc: no objection." if d.action == ALLOW else "")
        pf = mon.cfg.plan_file
        reason = (reason.replace(f" in `{pf}`", f" and submit it with {PLAN_TOOL}")
                  .replace(f"`{pf}`", PLAN_TOOL))
        return head + ("\n" + reason if reason else "")

    # ------------------------------------------------------------------ tools
    def start(self, request: str) -> str:
        sid = self._new_session()

        def fn(mon: Monitor) -> str:
            mon.state.sessions.append(sid)
            gap = mon.intent_gaps(request)
            return (f"skillc session {sid}.\n" + instructions(mon)
                    + ("\n\n" + gap if gap else ""))
        return self._run("start", {"request": request}, fn, sid)

    def check_plan(self, plan: str) -> str:
        return self._run("check_plan", {"plan": plan}, lambda m: m.submit_plan(plan))

    def check_reasoning(self, text: str) -> str:
        return self._run("check_reasoning", {"text": text}, lambda m: m.on_reasoning(text))

    @staticmethod
    def _tool(mon: Monitor, tool: str) -> str:
        """The name to give the monitor: a multi-purpose host tool becomes the runtime
        tool the approved plan uses (its first choice without a plan)."""
        name = tool.lower()
        choices = MULTI_TOOLS.get(name)
        if not choices:
            return name
        used = mon._plan_via()
        return next((c for c in choices if c in used), choices[0])

    def check_action(self, tool: str, details: str) -> str:
        return self._run("check_action", {"tool": tool, "details": details},
                         lambda m: m.pre_action(self._tool(m, tool), {"command": details}))

    def report_result(self, tool: str, details: str, output: str) -> str:
        return self._run("report_result", {"tool": tool, "details": details, "output": output},
                         lambda m: m.post_action(self._tool(m, tool), {"command": details},
                                                 output))

    def status(self) -> str:
        def fn(mon: Monitor) -> str:
            s = mon.state
            return json.dumps({"session": self._session(), "runtime": mon.runtime.name,
                               "approved_plan": bool(s.plan), "held": s.block,
                               "plans_refused_in_a_row": s.rejections,
                               "missing_programs": s.missing_programs,
                               "missing_resources": s.missing_resources,
                               "last": s.log[-5:]}, indent=1)
        return self._run("status", {}, fn)


def serve(root: Path, runtime: str, thinking: str = "ask") -> None:
    from mcp.server.fastmcp import FastMCP

    mm = McpMonitor(root, runtime, thinking)
    app = FastMCP("skillc", instructions=(
        "skillc checks whether the agent's plan and actions can succeed in this runtime. "
        "Call skillc_start first with the user's request, and follow what it says."))

    @app.tool()
    def skillc_start(request: str) -> str:
        """Call this first, once per task, with the user's request in their words. Returns
        how to write a plan skillc can check, and any requirement of the request this
        runtime cannot meet."""
        return mm.start(request)

    @app.tool()
    def skillc_check_plan(plan: str) -> str:
        """Submit your plan (SkillC Controlled English) before you act. DECISION allow: go
        ahead. DECISION deny: do not implement it; follow NEXT (replan, or ask_user)."""
        return mm.check_plan(plan)

    @app.tool()
    def skillc_check_reasoning(text: str) -> str:
        """When your reasoning changes course, send one or two sentences of what you now
        intend to do. skillc answers with a question if it heads somewhere impossible or
        prohibited here."""
        return mm.check_reasoning(text)

    @app.tool()
    def skillc_check_action(tool: str, details: str) -> str:
        """Before an action: the tool you will use (for example powershell, write, edit,
        browser, workiq, m_send_teams_message) and the command or content. DECISION deny:
        do not take this action; follow NEXT."""
        return mm.check_action(tool, details)

    @app.tool()
    def skillc_report_result(tool: str, details: str, output: str) -> str:
        """After an action: what it printed (errors included). skillc re-checks the plan
        against what the run showed."""
        return mm.report_result(tool, details, output)

    @app.tool()
    def skillc_status() -> str:
        """The approved plan, why actions are held (if they are), and what the run showed."""
        return mm.status()

    app.run()
