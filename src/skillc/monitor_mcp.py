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
  skillc_request_approval(...)           ask the USER (MCP elicitation) to approve one
                                         exact protected operation
  skillc_revoke_approval(approval)       withdraw an unused approval

This is advisory: the agent decides whether to call the tools and whether to follow
them.  Every answer starts with one line the agent can act on,

  DECISION: allow|deny|warn   NEXT: replan|ask_user   USER_NEEDS: a, b

followed by what skillc found (docs/RUNTIME_MONITOR.md, "stop, explain, re-plan").

The capabilities of the A365 runtime adapter are available here too (docs/SCOUT_PARITY.md):
`--strict` with a host-owned `--host-plan` (no plan replacement from the conversation,
named capabilities and known preconditions only, stale downstream facts invalidated),
and `--approval-policy` (protected operations need a single-use user approval bound to
their exact content, destinations, source and amount).

The state lives under `--root` (default ~/.skillc-mcp): `.skillc/monitor.json` (written
on first use), one state file per session, and `calls.jsonl`, a record of every call
and decision for evaluating a run afterwards (approval references are redacted).

  skillc monitor mcp --runtime scout-desktop [--root DIR] [--strict --host-plan FILE]
                     [--approval-policy FILE]
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .frontend.prompts import CE_DOC, CE_RUNTIME_DOC, CE_SOFTWARE_DOC
from .frontend.runtime import runtime_note
from .mcp_approvals import ApprovalPolicy, Approvals, PendingApproval
from .monitor import ALLOW, ASK_USER, DENY, Config, Decision, Monitor, state_lock
from .security import AuthorizationError

try:  # the MCP server is an optional extra; tool annotations resolve against this name
    from mcp.server.fastmcp import Context as McpContext
except ImportError:  # pragma: no cover - without the extra `serve` is unavailable anyway
    McpContext = None

MCP_TOOLS = ("skillc_start", "skillc_check_plan", "skillc_check_reasoning",
             "skillc_check_action", "skillc_report_result", "skillc_status",
             "skillc_request_approval", "skillc_revoke_approval")
POLICY = Path(".skillc") / "approval-policy.json"
REDACTED = "[approval reference redacted]"

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
    """One MCP server process: the monitor of the current session under `root`.

    `strict` requires `plan_text`, the host-owned plan, which is loaded into every session
    and cannot be replaced from the conversation. `policy` (default: the root's
    `.skillc/approval-policy.json`, when present) names the runtime tools whose actions
    need a single-use user approval of their exact content and destinations.
    """

    def __init__(self, root: Path, runtime: str, thinking: str = "ask", *,
                 strict: bool = False, plan_text: str | None = None,
                 policy: ApprovalPolicy | None = None):
        self.root = Path(root)
        cfg_path = self.root / CONFIG
        if not cfg_path.exists():
            cfg_path.parent.mkdir(parents=True, exist_ok=True)
            cfg_path.write_text(json.dumps(mcp_config(runtime, thinking).dump(), indent=1)
                                + "\n", encoding="utf-8")
        self.config = Config.load(cfg_path)
        self.config.strict = self.config.strict or strict
        if self.config.strict and not plan_text:
            raise ValueError("strict enforcement requires a host-owned plan (--host-plan)")
        self.plan_text = plan_text
        if policy is None and (self.root / POLICY).is_file():
            policy = ApprovalPolicy.load(self.root / POLICY)
        self.approvals = Approvals(self.root, policy) if policy else None

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
                if self.plan_text and mon.state.plan is None and not mon.state.block:
                    mon.load_plan(self.plan_text)
                out = fn(mon)
            finally:
                mon.save()
        if isinstance(out, Decision):
            out = self._render(mon, out)
        logged = {k: REDACTED if k == "approval" else str(v)[:2000] for k, v in args.items()}
        answer = out.split("\nAPPROVAL: ")[0] if "\nAPPROVAL: " in out else out
        with (self.root / ".skillc" / "calls.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "session": sid,
                                "call": call, "args": logged,
                                "answer": answer[:4000]}) + "\n")
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
            return (f"skillc session {sid}.\n" + instructions(mon) + self.guide()
                    + ("\n\n" + gap if gap else ""))
        return self._run("start", {"request": request}, fn, sid)

    def guide(self) -> str:
        """What the agent must know about strict mode and protected operations here."""
        out = ""
        if self.approvals:
            out += APPROVAL_GUIDE.format(tools=", ".join(sorted(
                self.approvals.policy.protected_tools)))
        if self.config.strict:
            out += STRICT_GUIDE
        return out

    def check_plan(self, plan: str) -> str:
        if self.config.strict:
            return self._run("check_plan", {"plan": plan}, lambda m: m._record("plan", Decision(
                DENY, "skillc: strict enforcement: the plan is owned by the host and cannot "
                      "be replaced from the conversation. Work within it, or tell the user "
                      "what it does not allow.", next=ASK_USER)))
        return self._run("check_plan", {"plan": plan}, lambda m: m.submit_plan(plan))

    def check_reasoning(self, text: str) -> str:
        return self._run("check_reasoning", {"text": text}, lambda m: m.on_reasoning(text))

    @staticmethod
    def _tool(mon: Monitor, tool: str) -> str:
        """The name to give the monitor: a Tool of the approved plan as is; otherwise the
        lower-cased host tool, a multi-purpose one becoming the runtime tool the approved
        plan uses (its first choice without a plan)."""
        if tool in (mon.plan_pack() or {}).get("capabilities", {}):
            return tool
        name = tool.lower()
        choices = MULTI_TOOLS.get(name)
        if not choices:
            return name
        used = mon._plan_via()
        return next((c for c in choices if c in used), choices[0])

    @staticmethod
    def _role(mon: Monitor, role: str) -> str | None:
        """The calling role: as given, or the plan's only role. Self-reported in Scout."""
        if role:
            return role
        roles = (mon.plan_pack() or {}).get("roles") or []
        return roles[0] if len(roles) == 1 else None

    @staticmethod
    def _operation(mon: Monitor, name: str) -> str:
        """The runtime tool that performs an action: a Tool's `via`, or the host mapping."""
        return mon._capability_via(name) or mon.cfg.tool_map.get(name, name)

    def check_action(self, tool: str, details: str, approval: str = "",
                     destinations: str = "", role: str = "", source_version: str = "",
                     source_text: str = "") -> str:
        sid = self._session()

        def fn(mon: Monitor) -> Decision:
            name = self._tool(mon, tool)
            d = mon.pre_action(name, {"command": details}, role=self._role(mon, role))
            operation = self._operation(mon, name)
            if d.action != ALLOW or not self.approvals or not self.approvals.protects(operation):
                return d
            try:
                self.approvals.consume(sid, approval, operation, destinations, details,
                                       source_version, source_text)
            except AuthorizationError as e:
                return mon._record("approval", Decision(
                    DENY, f"skillc: `{operation}` needs the user's approval of this exact "
                          f"operation ({e}). Call skillc_request_approval with the exact "
                          "content and destinations, then pass its APPROVAL here once.",
                    [operation], ASK_USER, ["user_approval"]), operation)
            return mon._record("approval", Decision(
                ALLOW, f"skillc: approved `{operation}` authorized once for exactly this "
                       "content and these destinations; do not change them."), operation)
        return self._run("check_action", {"tool": tool, "details": details,
                                          "approval": approval, "destinations": destinations,
                                          "role": role, "source_version": source_version},
                         fn, sid)

    def report_result(self, tool: str, details: str, output: str, role: str = "") -> str:
        return self._run("report_result", {"tool": tool, "details": details, "output": output,
                                           "role": role},
                         lambda m: m.post_action(self._tool(m, tool), {"command": details},
                                                 output, role=self._role(m, role)))

    # ------------------------------------------------------------------ approvals
    def prepare_approval(self, tool: str, destinations: str, content: str, source: str = "",
                         source_version: str = "", source_text: str = "",
                         amount: str = "") -> PendingApproval | str:
        """Validate an approval request; a PendingApproval to show the user, or a refusal.

        Grants nothing: only `finish_approval`, after the user's answer, can."""
        sid = self._session()
        out: list[PendingApproval] = []

        def fn(mon: Monitor) -> Decision:
            if not self.approvals:
                return Decision(DENY, "skillc: no approval policy is configured; nothing "
                                      "can be approved here.", next=ASK_USER)
            try:
                out.append(self.approvals.prepare(
                    sid, self._operation(mon, self._tool(mon, tool)), destinations, content,
                    source, source_version, source_text, amount))
            except (AuthorizationError, ValueError) as e:
                return mon._record("approval", Decision(
                    DENY, f"skillc: this operation cannot be approved: {e}", next=ASK_USER))
            return Decision(ALLOW, "skillc: asking the user to approve this exact operation.")
        answer = self._run("request_approval", {"tool": tool, "destinations": destinations,
                                                "source": source,
                                                "source_version": source_version}, fn, sid)
        return out[0] if out else answer

    def finish_approval(self, pending: PendingApproval, approved: bool | None,
                        audited: bool = False) -> str:
        """Record the user's answer. `approved` None: the host offered no user channel."""
        def fn(mon: Monitor) -> Decision:
            if approved is None:
                return mon._record("approval", Decision(
                    DENY, "skillc: this host did not provide a user-approval channel (MCP "
                          "elicitation), so the agent cannot obtain approval; ask the user "
                          "to perform the operation themselves.", next=ASK_USER,
                    user_needs=["user_approval"]))
            if not approved:
                return mon._record("approval", Decision(
                    DENY, "skillc: the user did not approve this operation; do not perform "
                          "it.", next=ASK_USER))
            try:
                token = self.approvals.grant(pending, audited=audited)
            except AuthorizationError as e:
                return mon._record("approval", Decision(
                    DENY, f"skillc: approval refused: {e}", next=ASK_USER))
            mon._record("approval", Decision(ALLOW, "user approved"), pending.delivery.operation)
            return Decision(ALLOW, "skillc: the user approved this exact operation. Pass "
                                   "the reference below to skillc_check_action, once, with "
                                   "the same content and destinations.\nAPPROVAL: " + token)
        return self._run("approval_answer", {"approved": approved, "audited": audited},
                         fn, pending.session)

    def request_approval(self, tool: str, destinations: str, content: str,
                         confirm, **kwargs) -> str:
        """prepare, ask `confirm(summary) -> (approved, audited) | None`, finish."""
        pending = self.prepare_approval(tool, destinations, content, **kwargs)
        if isinstance(pending, str):
            return pending
        answer = confirm(pending.summary)
        if answer is None:
            return self.finish_approval(pending, None)
        return self.finish_approval(pending, *answer)

    def revoke_approval(self, approval: str) -> str:
        sid = self._session()

        def fn(mon: Monitor) -> Decision:
            if not self.approvals:
                return Decision(DENY, "skillc: no approval policy is configured.")
            try:
                self.approvals.revoke(sid, approval)
            except AuthorizationError as e:
                return Decision(DENY, f"skillc: {e}")
            return mon._record("approval", Decision(ALLOW, "skillc: approval revoked."))
        return self._run("revoke_approval", {"approval": approval}, fn, sid)

    def status(self) -> str:
        def fn(mon: Monitor) -> str:
            s = mon.state
            return json.dumps({"session": self._session(), "runtime": mon.runtime.name,
                               "approved_plan": bool(s.plan), "held": s.block,
                               "plans_refused_in_a_row": s.rejections,
                               "missing_programs": s.missing_programs,
                               "missing_resources": s.missing_resources,
                               "strict": self.config.strict,
                               "host_owned_plan": bool(self.plan_text),
                               "protected_tools": sorted(self.approvals.policy.protected_tools)
                               if self.approvals else [],
                               "last": s.log[-5:]}, indent=1)
        return self._run("status", {}, fn)


APPROVAL_GUIDE = (
    "\nPROTECTED OPERATIONS: actions through {tools} need the user's approval of their exact "
    "content and destinations. Call skillc_request_approval first (the user is asked "
    "directly), then pass the returned APPROVAL to skillc_check_action once, with the same "
    "content and destinations. A changed message, recipient or source needs a new approval.")
STRICT_GUIDE = (
    "\nSTRICT: the plan is owned by the host; skillc_check_plan cannot replace it. Name the "
    "plan's Tool (not the host tool) in skillc_check_action and skillc_report_result.")


def serve(root: Path, runtime: str, thinking: str = "ask", *, strict: bool = False,
          host_plan: Path | None = None, policy_path: Path | None = None) -> None:
    from mcp.server.fastmcp import FastMCP
    from pydantic import BaseModel, Field

    plan_text = Path(host_plan).read_text(encoding="utf-8") if host_plan else None
    policy = ApprovalPolicy.load(policy_path) if policy_path else None
    mm = McpMonitor(root, runtime, thinking, strict=strict, plan_text=plan_text, policy=policy)
    guide = mm.guide()
    app = FastMCP("skillc", instructions=(
        "skillc checks whether the agent's plan and actions can succeed in this runtime. "
        "Call skillc_start first with the user's request, and follow what it says." + guide))

    class ApprovalForm(BaseModel):
        approve: bool = Field(description="Approve exactly this operation, once")
        audited: bool = Field(default=False, description="An independent audit was "
                              "completed (required above the policy's audit amount)")

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
    def skillc_check_action(tool: str, details: str, approval: str = "",
                            destinations: str = "", role: str = "",
                            source_version: str = "", source_text: str = "") -> str:
        """Before an action: the tool you will use (for example powershell, write, edit,
        browser, workiq, m_send_teams_message; the plan's Tool name in strict mode) and
        the command or exact content. For a protected operation also pass the APPROVAL
        reference and its comma-separated destinations. DECISION deny: do not take this
        action; follow NEXT."""
        return mm.check_action(tool, details, approval, destinations, role, source_version,
                               source_text)

    @app.tool()
    def skillc_report_result(tool: str, details: str, output: str, role: str = "") -> str:
        """After an action: what it printed (errors included). skillc re-checks the plan
        against what the run showed."""
        return mm.report_result(tool, details, output, role)

    @app.tool()
    def skillc_status() -> str:
        """The approved plan, why actions are held (if they are), and what the run showed."""
        return mm.status()

    @app.tool()
    async def skillc_request_approval(tool: str, destinations: str, content: str,
                                      ctx: McpContext, source: str = "",
                                      source_version: str = "", source_text: str = "",
                                      amount: str = "") -> str:
        """Ask the USER to approve one exact protected operation: the tool, comma-separated
        destinations (all recipients), the exact content, and optionally the source it was
        derived from and a monetary amount. Returns APPROVAL on approval. You cannot
        approve it yourself."""
        pending = mm.prepare_approval(tool, destinations, content, source, source_version,
                                      source_text, amount)
        if isinstance(pending, str):
            return pending
        try:
            result = await ctx.elicit("skillc: approve this exact operation?\n\n"
                                      + pending.summary, ApprovalForm)
        except Exception:  # noqa: BLE001 - a host without elicitation offers no channel
            return mm.finish_approval(pending, None)
        accepted = result.action == "accept" and bool(result.data.approve)
        audited = bool(result.data.audited) if result.action == "accept" else False
        return mm.finish_approval(pending, accepted, audited)

    @app.tool()
    def skillc_revoke_approval(approval: str) -> str:
        """Withdraw an approval you no longer use (for example, after the source changed)."""
        return mm.revoke_approval(approval)

    app.run()
