"""Microsoft Agent Framework adapter for the runtime monitor (docs/RUNTIME_MONITOR.md).

The monitor core (skillc.monitor) is attached to an `Agent` as two middleware objects:

  SkillcFunctionMiddleware   every tool call of the agent loop, including MCP tools the
                             agent connected to (a Foundry toolbox): `pre_action` before
                             the call, `post_action` after it.  A refusal is a normal tool
                             result the model reads ({"skillc": "blocked", "reason": ...});
                             `call_next()` is not called and `terminate` is never set, so
                             the conversation stays consistent and the model can act on
                             the reason (spike fact F2 in docs/HOSTED_AGENT.md).
  SkillcAgentMiddleware      the run: the user's request is given to `on_prompt` and any
                             context (the intent check, the plan instructions when the plan
                             tool is enabled) is appended as a user-role message; the
                             response text goes to `on_reasoning`, observe-only.

One `SkillcMonitor` holds one monitor core, shared by the middleware of every agent of
the process; `middleware_for(role)` gives each role agent its own pair, so that the
ownership of the plan's Tools is enforced per role.  The state lives in
`root/<session>/state.json` and survives an idle/resume of a hosted agent.

Fail-open.  Every entry point is wrapped: an internal exception is logged once at
WARNING and the call is allowed (`fail_open=True`, the default).  The monitor never stops
an agent by crashing.  `SKILLC_MONITOR=off` in the environment makes `middleware_for`
return nothing.

Usage, in the hosted agent's main.py:

    from skillc.integrations.agent_framework import skillc_monitor

    monitor = skillc_monitor(runtime="foundry-hosted", root=Path.home() / ".skillc",
                             plan_path=Path("protocol/quarterly_finance_report.ce"),
                             agent_tools=ROLES)
    role_agent = Agent(client=client, tools=[...], middleware=monitor.middleware_for("Writer"))
    coordinator = Agent(client=client, tools=[*role_tools, *monitor.tools],
                        middleware=monitor.middleware_for())
"""
from __future__ import annotations

import logging
import os
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Annotated, Any

try:
    from agent_framework import (AgentContext, AgentMiddleware, Content, FunctionInvocationContext,
                                 FunctionMiddleware, Message, tool)
except ImportError as e:  # pragma: no cover - exercised only without the extra
    raise ImportError(
        "skillc.integrations.agent_framework needs Microsoft Agent Framework: "
        "pip install 'skillc[agent-framework]' (agent-framework-core>=1.19,<2)") from e

from ..monitor import (ALLOW, DENY, Config, Decision, Monitor, Rule, state_lock,
                       tool_map_from_names)

PLAN_TOOL = "skillc_write_plan"
ENV_SWITCH = "SKILLC_MONITOR"
REPEAT_LIMIT = 5          # identical denials before the reason tells the model to stop
STOP_NOTE = "stop and tell the user what is missing; do not retry. "


class SkillcMonitor:
    """The monitor of one process: one core, one state file per session, middleware per
    role.

    `plan_text` or `plan_path` is a plan approved before the run (the protocol pack): it
    is loaded at construction with `Monitor.load_plan`, its verdict is logged, and when it
    is not ACHIEVABLE no action is approved (the verdict is in `plan_decision` and in
    `status()`); nothing is raised.  Without a pre-approved plan the agent writes its plan
    with the `skillc_write_plan` tool (`tools`); `enable_plan_tool` overrides that default.
    `agent_tools` are the names of the sub-agent handoffs (a coordinator's role tools):
    always allowed, never a change of protocol state.
    """

    def __init__(self, *, runtime: str = "foundry-hosted", root: Path,
                 plan_path: Path | None = None, plan_text: str | None = None,
                 session_id: str | None = None, agent_tools: Iterable[str] = (),
                 prohibited: list[dict] | None = None, thinking: str = "off",
                 fail_open: bool = True, logger: logging.Logger | None = None,
                 enable_plan_tool: bool | None = None):
        self.log = logger or logging.getLogger("skillc.agent_framework")
        self.root = Path(root)
        self.session_id = session_id or os.environ.get("FOUNDRY_AGENT_SESSION_ID") or "default"
        self.fail_open = fail_open
        self.plan_decision: Decision | None = None
        self.core: Monitor | None = None
        self._denials: dict[str, int] = {}
        self._off_logged = False
        self._plan_tool: Any = None
        rules = [r if isinstance(r, Rule) else Rule(**r) for r in (prohibited or [])]
        self.cfg = Config(runtime=runtime, plan_file="{session}/plan.ce",
                          state_file="{session}/state.json", thinking=thinking,
                          free_tools=(PLAN_TOOL,), tool_map={}, plan_tools=(PLAN_TOOL,),
                          agent_tools=tuple(agent_tools), prohibited=rules)
        try:
            if plan_text is None and plan_path is not None:
                plan_text = Path(plan_path).read_text(encoding="utf-8")
            self.enable_plan_tool = (plan_text is None if enable_plan_tool is None
                                     else enable_plan_tool)
            core = Monitor(self.cfg, self.root, session_id=self.session_id)
            if plan_text is not None:
                with state_lock(core.state_path):
                    try:
                        self.plan_decision = core.load_plan(plan_text)
                    finally:
                        core.save()
                level = logging.INFO if self.plan_decision.action == ALLOW else logging.WARNING
                self.log.log(level, "skillc plan verdict (session %s): %s", self.session_id,
                             self.plan_decision.reason.splitlines()[0])
            self.core = core
        except Exception as e:  # noqa: BLE001 - the monitor never stops the agent
            self.enable_plan_tool = bool(enable_plan_tool)
            self._fail("construction", e)

    # ------------------------------------------------------------------ public API
    def middleware_for(self, role: str | None = None) -> list:
        """The two middleware objects for one agent; `role` is its role in the plan, so that
        a Tool owned by another role is refused.  Empty when SKILLC_MONITOR=off."""
        if os.environ.get(ENV_SWITCH, "").lower() == "off":
            if not self._off_logged:
                self.log.info("skillc monitor disabled by %s=off", ENV_SWITCH)
                self._off_logged = True
            return []
        return [SkillcFunctionMiddleware(self, role), SkillcAgentMiddleware(self, role)]

    @property
    def tools(self) -> list:
        """The agent's skillc tools: `skillc_write_plan` when the plan tool is enabled."""
        if not self.enable_plan_tool:
            return []
        if self._plan_tool is None:
            self._plan_tool = self._make_plan_tool()
        return [self._plan_tool]

    def status(self) -> dict:
        """The plan verdict, the protocol state and the tail of the decision log."""
        out: dict[str, Any] = {
            "session": self.session_id, "active": self.core is not None,
            "plan": self.plan_decision.to_dict() if self.plan_decision else None}
        if self.core is not None:
            st = self.core.state
            out.update({"approved": st.plan is not None, "block": st.block, "facts": list(st.facts),
                        "actions": list(st.actions), "log": st.log[-20:],
                        "state_file": str(self.core.state_path)})
        return out

    def submit_plan(self, text: str) -> Decision:
        """Check a plan written during the run (the `skillc_write_plan` tool)."""
        if self.core is None:
            return Decision(ALLOW, "skillc: the monitor is not active; the plan was not checked.")
        try:
            return self._transaction(lambda core: core.submit_plan(text))
        except Exception as e:  # noqa: BLE001
            if not self.fail_open:
                raise
            self.log.warning("skillc monitor (plan): %s", e)
            return Decision(DENY, f"skillc: the plan could not be checked ({e}); "
                                  "simplify it and submit it again.")

    # ------------------------------------------------------------------ core transactions
    def _transaction(self, fn: Callable[[Monitor], Decision]) -> Decision:
        core = self.core
        assert core is not None
        with state_lock(core.state_path):
            try:
                return fn(core)
            finally:
                core.save()

    def _fail(self, what: str, e: Exception) -> None:
        if not self.fail_open:
            raise e
        self.log.warning("skillc monitor (%s): %s; allowing", what, e)

    def _pre(self, name: str, args: dict, role: str | None) -> Decision:
        if self.core is None:
            return Decision(ALLOW)
        try:
            core = self.core
            caps = (core.plan_pack() or {}).get("capabilities", {})
            if name not in core.cfg.tool_map and name not in caps:
                core.cfg.tool_map.update(tool_map_from_names([name], core.runtime))
            d = self._transaction(lambda c: c.pre_action(name, args, role=role))
        except Exception as e:  # noqa: BLE001
            self._fail(f"pre {name}", e)
            return Decision(ALLOW)
        return self._repeat_guard(d) if d.action == DENY else d

    def _post(self, name: str, args: dict, result: Any, role: str | None) -> Decision:
        if self.core is None:
            return Decision(ALLOW)
        try:
            value = result_value(result)
            return self._transaction(lambda c: c.post_action(name, args, value, role=role))
        except Exception as e:  # noqa: BLE001
            self._fail(f"post {name}", e)
            return Decision(ALLOW)

    def _prompt(self, text: str) -> list[str]:
        if self.core is None:
            return []
        try:
            core = self.core
            with state_lock(core.state_path):
                try:
                    if self.enable_plan_tool:
                        return core.on_prompt(text, self.session_id)
                    gap = core.intent_gaps(text)
                    return [gap] if gap else []
                finally:
                    core.save()
        except Exception as e:  # noqa: BLE001
            self._fail("prompt", e)
            return []

    def _reasoning(self, text: str) -> Decision:
        if self.core is None or not text:
            return Decision(ALLOW)
        try:
            return self._transaction(lambda c: c.on_reasoning(text))
        except Exception as e:  # noqa: BLE001
            self._fail("reasoning", e)
            return Decision(ALLOW)

    def _repeat_guard(self, d: Decision) -> Decision:
        """After REPEAT_LIMIT identical denials the reason tells a looping model to stop."""
        n = self._denials.get(d.reason, 0) + 1
        self._denials[d.reason] = n
        if n > REPEAT_LIMIT:
            return Decision(DENY, STOP_NOTE + d.reason, d.witness)
        return d

    def _make_plan_tool(self):
        monitor = self

        @tool(name=PLAN_TOOL,
              description="Submit your plan in SkillC Controlled English. Returns skillc's "
                          "verdict; only a plan judged ACHIEVABLE lets implementing tools run.")
        def skillc_write_plan(
                plan: Annotated[str, "The whole plan, in SkillC Controlled English."]) -> str:
            return monitor.submit_plan(plan).reason

        return skillc_write_plan


def skillc_monitor(**kwargs) -> SkillcMonitor:
    """`SkillcMonitor(**kwargs)`: see the class for the arguments."""
    return SkillcMonitor(**kwargs)


# ---------------------------------------------------------------------- middleware

class SkillcFunctionMiddleware(FunctionMiddleware):
    """The action gate: `pre_action` before every tool call, `post_action` after it."""

    def __init__(self, monitor: SkillcMonitor, role: str | None = None):
        self.monitor = monitor
        self.role = role

    async def process(self, context: FunctionInvocationContext,
                      call_next: Callable[[], Any]) -> None:
        try:
            name = str(getattr(context.function, "name", None) or context.function)
            args = arguments_dict(context.arguments)
        except Exception as e:  # noqa: BLE001
            self.monitor._fail("function context", e)
            await call_next()
            return
        d = self.monitor._pre(name, args, self.role)
        telemetry_span("pre", name, self.role, d)
        if d.action == DENY:
            context.result = {"skillc": "blocked", "reason": d.reason}
            return
        await call_next()
        post = self.monitor._post(name, args, context.result, self.role)
        if post.action != ALLOW:
            telemetry_span("post", name, self.role, post)
        if post.action != ALLOW and post.reason:
            try:
                context.result = annotate(context.result, post.reason)
            except Exception as e:  # noqa: BLE001
                self.monitor._fail(f"annotate {name}", e)


class SkillcAgentMiddleware(AgentMiddleware):
    """The prompt and reasoning signals of one run; observe-only."""

    def __init__(self, monitor: SkillcMonitor, role: str | None = None):
        self.monitor = monitor
        self.role = role

    async def process(self, context: AgentContext, call_next: Callable[[], Any]) -> None:
        try:
            ctx = self.monitor._prompt(last_user_text(context.messages))
            if ctx:
                context.messages.append(Message(role="user", contents=["\n\n".join(ctx)]))
        except Exception as e:  # noqa: BLE001
            self.monitor._fail("agent context", e)
        await call_next()
        try:
            if not getattr(context, "stream", False) and context.result is not None:
                text = getattr(context.result, "text", None)
                if isinstance(text, str) and text:
                    self.monitor._reasoning(text)
        except Exception as e:  # noqa: BLE001
            self.monitor._fail("agent result", e)


# ---------------------------------------------------------------------- telemetry

def telemetry_span(phase: str, tool: str, role: str | None, decision: Decision) -> None:
    """One OpenTelemetry span per decision, `skillc.decision <phase> <allow|deny|warn> <tool>`,
    so a hosted agent's decisions appear next to its tool spans in Application Insights
    (the platform configures the exporter). A no-op when OpenTelemetry is not installed;
    never raises."""
    try:
        from ..telemetry import event
        event(f"skillc.decision {phase} {decision.action} {tool}", phase=phase, tool=tool,
              role=role or "", action=decision.action, reason=(decision.reason or "")[:500])
    except Exception:  # noqa: BLE001 - telemetry must never affect the decision
        return


# ---------------------------------------------------------------------- shapes

def arguments_dict(arguments: Any) -> dict:
    """`context.arguments` as a plain dict: a dict as is (spike fact F3), a pydantic model
    through `model_dump()`, anything else empty."""
    if isinstance(arguments, dict):
        return arguments
    dump = getattr(arguments, "model_dump", None)
    if callable(dump):
        out = dump()
        return out if isinstance(out, dict) else {}
    try:
        return dict(arguments) if arguments is not None else {}
    except (TypeError, ValueError):
        return {}


def result_value(result: Any) -> Any:
    """What the monitor's failure rule and observations see: the text of a `list[Content]`
    (what `call_next()` leaves after `FunctionTool.invoke`), a str or dict unchanged, an
    empty string for None, otherwise `str(result)`."""
    if result is None:
        return ""
    if isinstance(result, (str, dict)):
        return result
    if isinstance(result, list):
        parts = [c.text for c in result if isinstance(getattr(c, "text", None), str)]
        return "\n".join(parts) if parts else "\n".join(str(c) for c in result)
    return str(result)


def annotate(result: Any, note: str) -> Any:
    """The result with skillc's observation appended, so that the model sees it."""
    if isinstance(result, dict):
        return {**result, "skillc": note}
    if isinstance(result, list):
        return [*result, Content.from_text("skillc: " + note)]
    if result is None:
        return "skillc: " + note
    return str(result) + "\n\nskillc: " + note


def last_user_text(messages: Any) -> str:
    """The text of the last user-role message of a run's input."""
    try:
        for m in reversed(list(messages or [])):
            role = str(getattr(m, "role", "")).lower()
            if role.endswith("user"):
                text = getattr(m, "text", "")
                return text if isinstance(text, str) else ""
    except TypeError:
        return ""
    return ""
