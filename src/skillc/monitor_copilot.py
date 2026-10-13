"""GitHub Copilot hook adapter for the runtime monitor (docs/RUNTIME_MONITOR.md).

Serves Copilot CLI and the Copilot cloud (coding) agent through their hooks,
configured in `.github/hooks/*.json`.  Nothing here calls a model API: the
monitor is deterministic and the hooks are the only channel.

  skillc monitor hook copilot sessionStart         plan protocol + intent check (once per session)
  skillc monitor hook copilot userPromptSubmitted  intent check, queued (config hooks cannot add
                                                   context on this event)
  skillc monitor hook copilot preToolUse           the action before it runs: deny with a reason
  skillc monitor hook copilot postToolUse          observe the result, re-check the plan, deliver
                                                   queued context
  skillc monitor hook copilot postToolUseFailure   observe the error (exit 2: stdout is context)
  skillc monitor hook copilot agentStop            scan the turn's transcript for reasoning that
                                                   heads to the impossible; block the stop once

Input is the hook's JSON on stdin, in Copilot's camelCase form (`toolName`,
`toolArgs` as a JSON string, `toolResult.textResultForLlm`) or the VS
Code-compatible snake_case form (`tool_name`, `tool_input`, `tool_result`).
Output is the event's JSON on stdout.

Copilot treats a non-zero exit of a preToolUse hook as a denial, so an
internal error here is written to stderr and exits 0: the monitor never
stops the agent by crashing.  Where `.skillc/monitor.json` is absent, the
hooks do nothing.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .monitor import ALLOW, DENY, WARN, Config, Monitor, state_lock, thinking_since
from .monitor_hook import CONFIG, _root

# Copilot tool -> runtime tool (the vocabulary of the runtime manifests)
COPILOT_TOOL_MAP = {"bash": "bash", "powershell": "bash", "create": "write", "edit": "edit",
                    "view": "read", "web_fetch": "web_fetch", "web_search": "web_search",
                    "task": "agent_spawn"}
# tools that only look around or talk to the user: allowed before a plan exists
COPILOT_FREE_TOOLS = ("view", "grep", "glob", "web_search", "update_todo", "ask_user")
COPILOT_PLAN_TOOLS = ("create",)
HOOKS_FILE = Path(".github") / "hooks" / "skillc.json"


def copilot_config(runtime: str, thinking: str) -> Config:
    return Config(runtime=runtime, thinking=thinking, tool_map=dict(COPILOT_TOOL_MAP),
                  free_tools=COPILOT_FREE_TOOLS, plan_tools=COPILOT_PLAN_TOOLS)


def copilot_hooks(command: str = "skillc monitor hook copilot", timeout: int = 60) -> dict:
    """The `.github/hooks/skillc.json` document: one command hook per event."""
    def hook(event: str) -> dict:
        return {"type": "command", "bash": f"{command} {event}",
                "powershell": f"{command} {event}", "timeoutSec": timeout}
    return {"version": 1, "hooks": {e: [hook(e)] for e in (
        "sessionStart", "userPromptSubmitted", "preToolUse", "postToolUse",
        "postToolUseFailure", "agentStop")}}


# --------------------------------------------------------------------------
# Input
# --------------------------------------------------------------------------

def normalize(event: dict) -> dict:
    """One shape from the camelCase and the VS Code-compatible snake_case events."""
    def pick(*keys, default=None):
        for k in keys:
            if event.get(k) is not None:
                return event[k]
        return default

    args = pick("toolArgs", "tool_input", default={})
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {"raw": args}
    if not isinstance(args, dict):
        args = {}
    result = pick("toolResult", "tool_result", default="")
    if isinstance(result, dict):
        result = (result.get("textResultForLlm") or result.get("text_result_for_llm")
                  or json.dumps(result, default=str))
    error = pick("error", default="")
    if isinstance(error, dict):
        error = error.get("message") or json.dumps(error, default=str)
    return {"session_id": str(pick("sessionId", "session_id", default="")),
            "cwd": str(pick("cwd", default="")),
            "tool_name": str(pick("toolName", "tool_name", default="")),
            "tool_input": args,
            "tool_result": result if isinstance(result, str) else json.dumps(result, default=str),
            "error": error if isinstance(error, str) else json.dumps(error, default=str),
            "prompt": str(pick("prompt", "initialPrompt", "initial_prompt", default="")),
            "transcript_path": str(pick("transcriptPath", "transcript_path", default="")),
            "stop_hook_active": bool(pick("stop_hook_active", "stopHookActive", default=False))}


# --------------------------------------------------------------------------
# Handlers: each returns (payload, exit code); a dict payload is printed as JSON,
# a string as is, None prints nothing.
# --------------------------------------------------------------------------

def _flush(mon: Monitor) -> list[str]:
    ctx, mon.state.pending = list(mon.state.pending), []
    return ctx


def _context(ctx: list[str]) -> tuple[dict | None, int]:
    return ({"additionalContext": "\n\n".join(ctx)} if ctx else None), 0


def _on_session_start(mon: Monitor, ev: dict) -> tuple[dict | None, int]:
    prompt = ev["prompt"] or os.environ.get("COPILOT_AGENT_PROMPT", "")
    return _context(mon.on_prompt(prompt, ev["session_id"]))


def _on_prompt(mon: Monitor, ev: dict) -> tuple[None, int]:
    # Configuration-file hooks cannot add context on this event (only SDK hooks may
    # rewrite the prompt), so what we have to say waits for the next postToolUse.  The
    # instructions are included in case sessionStart was not hooked.
    mon.state.pending.extend(mon.on_prompt(ev["prompt"], ev["session_id"]))
    return None, 0


def _on_pre(mon: Monitor, ev: dict) -> tuple[dict | None, int]:
    d = mon.pre_action(ev["tool_name"], ev["tool_input"])
    if d.action == DENY:
        return {"permissionDecision": "deny", "permissionDecisionReason": d.reason}, 0
    if d.reason:                        # an approved plan: the agent hears it at the next chance
        mon.state.pending.append(d.reason)
    return None, 0                      # no decision: Copilot's own permission rules apply


def _on_post(mon: Monitor, ev: dict) -> tuple[dict | None, int]:
    d = mon.post_action(ev["tool_name"], ev["tool_input"], ev["tool_result"])
    ctx = _flush(mon)
    if d.action != ALLOW:
        ctx.append(d.reason)
    return _context(ctx)


def _on_post_failure(mon: Monitor, ev: dict) -> tuple[str | None, int]:
    d = mon.post_action(ev["tool_name"], ev["tool_input"], ev["error"])
    ctx = _flush(mon)
    if d.action != ALLOW:
        ctx.append(d.reason)
    if not ctx:
        return None, 0
    return "\n\n".join(ctx), 2          # exit 2: stdout is appended to the failure as context


def _on_stop(mon: Monitor, ev: dict) -> tuple[dict | None, int]:
    """The turn's reasoning is only reachable here, through the transcript."""
    if not ev["transcript_path"]:
        return None, 0
    transcript = Path(ev["transcript_path"])
    offsets = mon.state.transcript_offsets
    text, offsets[str(transcript)] = thinking_since(transcript, offsets.get(str(transcript), 0))
    d = mon.observe_thinking(text)
    if d.action == DENY and not ev["stop_hook_active"]:
        return {"decision": "block", "reason": d.reason}, 0
    if d.action in (DENY, WARN):
        mon.state.pending.append(d.reason)
    return None, 0


_HANDLERS = {"sessionstart": _on_session_start,
             "userpromptsubmitted": _on_prompt, "userpromptsubmit": _on_prompt,
             "pretooluse": _on_pre, "posttooluse": _on_post,
             "posttoolusefailure": _on_post_failure,
             "agentstop": _on_stop, "stop": _on_stop}


def handle(event_name: str, event: dict) -> int:
    handler = _HANDLERS.get(event_name.replace("_", "").lower())
    if handler is None:
        raise ValueError(f"unknown Copilot hook event {event_name!r}; "
                         f"known: {sorted(_HANDLERS)}")
    root = _root(event)
    if root is None:
        return 0                                   # monitor not configured here
    ev = normalize(event)
    config = Config.load(root / CONFIG).for_session(ev["session_id"])
    with state_lock(root / config.state_file):
        mon = Monitor(config, root, session_id=ev["session_id"])
        try:
            payload, code = handler(mon, ev)
        finally:
            mon.save()
    if isinstance(payload, dict):
        print(json.dumps(payload))
    elif isinstance(payload, str):
        print(payload)
    return code


def main(event_name: str) -> int:
    raw = sys.stdin.read()
    try:
        return handle(event_name, json.loads(raw) if raw.strip() else {})
    except Exception as e:  # noqa: BLE001 - a crash must not deny the agent's every tool
        print(f"skillc monitor (copilot {event_name}): {e}", file=sys.stderr)
        return 0
