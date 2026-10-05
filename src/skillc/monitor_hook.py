"""Claude Code hook adapter for the runtime monitor (docs/RUNTIME_MONITOR.md).

  skillc monitor hook prompt   UserPromptSubmit: plan protocol + intent check (once per session)
  skillc monitor hook pre      PreToolUse: reasoning since the last call, then the action
  skillc monitor hook post     PostToolUse: observe the result, re-check the plan

Reads the hook's JSON from stdin; the monitor is active only where
`.skillc/monitor.json` exists (in the hook's cwd or $CLAUDE_PROJECT_DIR).
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .frontend.toolpolicy import match, unmet
from .monitor import ALLOW, DENY, Config, Monitor, plan_instructions, thinking_since

CONFIG = Path(".skillc") / "monitor.json"


def _root(event: dict) -> Path | None:
    for base in (os.environ.get("CLAUDE_PROJECT_DIR"), event.get("cwd"), "."):
        if base and (Path(base) / CONFIG).exists():
            return Path(base)
    return None


def _emit(event_name: str, **fields) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": event_name, **fields}}))


def handle(kind: str, event: dict) -> int:
    root = _root(event)
    if root is None:
        return 0                                   # monitor not configured here
    handler = _HANDLERS.get(kind)
    if handler is None:
        raise ValueError(f"unknown hook kind {kind!r}")
    mon = Monitor(Config.load(root / CONFIG), root)
    try:
        handler(mon, event)
    finally:
        mon.save()
    return 0


def _on_prompt(mon: Monitor, event: dict) -> None:
    ctx = []
    sid = event.get("session_id", "")
    if sid not in mon.state.sessions:
        mon.state.sessions.append(sid)
        ctx.append(plan_instructions(mon.runtime, mon.cfg.plan_file))
    prompt = event.get("prompt") or event.get("prompt_text") or ""
    rt, lib = mon.effective()
    gaps = [o for o in match(prompt, lib) if unmet(o, rt, lib)]
    if gaps:
        ctx.append("skillc intent check: the request mentions requirements runtime "
                   f"`{rt.name}` cannot meet: " + "; ".join(
                       f"'{o.text}' needs {o.clause()}" for o in gaps)
                   + ". Plan around them or tell the user.")
    if ctx:
        _emit("UserPromptSubmit", additionalContext="\n\n".join(ctx))


def _on_pre(mon: Monitor, event: dict) -> None:
    tool_input = event.get("tool_input") or {}
    if event.get("transcript_path"):
        text, mon.state.transcript_offset = thinking_since(
            Path(event["transcript_path"]), mon.state.transcript_offset)
        t = mon.observe_thinking(text)
        if t.action == DENY and not mon.is_plan_file(tool_input):
            _emit("PreToolUse", permissionDecision="deny",
                  permissionDecisionReason=t.reason)
            return
    d = mon.pre_action(event.get("tool_name", ""), tool_input)
    if d.action == DENY:
        _emit("PreToolUse", permissionDecision="deny", permissionDecisionReason=d.reason)
    elif d.reason:
        _emit("PreToolUse", additionalContext=d.reason)


def _on_post(mon: Monitor, event: dict) -> None:
    result = event.get("tool_response", event.get("tool_result", ""))
    d = mon.post_action(event.get("tool_name", ""), event.get("tool_input") or {}, result)
    if d.action != ALLOW:
        _emit("PostToolUse", additionalContext=d.reason)


_HANDLERS = {"prompt": _on_prompt, "pre": _on_pre, "post": _on_post}


def main(kind: str) -> int:
    raw = sys.stdin.read()
    return handle(kind, json.loads(raw) if raw.strip() else {})
