"""The two LLM columns of tab 1: a plain LLM check and an LLM check with a guiding skill.

Both get the same skill and the same facts about each place it could run (tool names; for this
machine also which tools ask first, the MCP servers and the credential names that are set).
Only the guided check also gets a guiding skill: where to start, look at the tools first, then
how the agent may interact (permissions, servers, credentials), and when to answer UNKNOWN.

Every request goes through `skillc.frontend.providers`, which refuses unless
SKILLC_ALLOW_MODEL_CALLS=1 and scrubs URLs, host names and e-mail addresses before sending.
Settings are sent under neutral ids, never with paths. One call per check answers for every
setting at once.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from skillc.frontend import providers  # noqa: E402

ARMS = ("plain", "guided")
VERDICTS = ("ACHIEVABLE", "IMPOSSIBLE", "UNKNOWN")
# names sent to the model: no domain-like labels
DESCRIBE = {"this machine": "the user's own GitHub Copilot CLI, in this folder",
            "Copilot CLI": "GitHub Copilot CLI (standard tool list)",
            "VS Code Copilot": "GitHub Copilot agent mode in VS Code (standard tool list)",
            "Claude Code": "Claude Code (standard tool list)",
            "claude.ai": "the Claude consumer app (standard tool list)"}

SYSTEM = """You decide whether an AI agent could complete a skill (a task description) in each of
several runtimes, using only the tools each runtime has. Return one JSON object and nothing else:
{"settings": {"<id>": {"verdict": "ACHIEVABLE" | "IMPOSSIBLE" | "UNKNOWN",
                       "missing": ["<tool the runtime lacks>", ...],
                       "reason": "<one short sentence>"}}}
Answer for every id you are given."""

GUIDE = """Guiding skill: check the environment before you decide.
1. Start with the skill: what does "finished" mean, and which steps lead there?
2. Look at the tools first: list the tools each runtime has, exactly as named.
3. Match every step to a tool. The same tool can have another name in another runtime (a
   question to the user may be ask_user_input_v0, ask_user or AskUserQuestion); count it only
   when it clearly does the same job, and say which tool you matched. A step no tool can do
   makes the skill IMPOSSIBLE there; name the missing tool under "missing".
4. See how the agent may interact: a tool that "asks first" needs the user's approval, which
   is allowed; a denied tool is missing. MCP servers count only for tools they list.
   A credential name being set does not prove the account works.
5. If the skill does not say what finished means, or you cannot tell which tool a step needs,
   answer UNKNOWN rather than guessing."""


def transcribe_sketch(image: bytes, mime: str, *, provider: str, model: str | None,
                      timeout: int = 180, complete=None) -> dict:
    """A picture of a building sketch -> sketch text in the reader's line format. The model
    only transcribes; the deterministic reader (`skillc.env.twin_sketch`) decides what the
    text means, and the user reviews the text first."""
    complete = complete or providers.complete
    started = time.perf_counter()
    with providers.metered() as usage:
        text = complete(provider, TRANSCRIBE, "Transcribe this building sketch.", model,
                        timeout, json_mode=False, image=(image, mime))
    lines = [ln.rstrip() for ln in text.strip().strip("`").splitlines()]
    return {"text": "\n".join(ln for ln in lines if ln.strip() and not ln.startswith("```")),
            "ms": round((time.perf_counter() - started) * 1000),
            "input_tokens": sum(int(u.get("input_tokens", 0)) for u in usage),
            "output_tokens": sum(int(u.get("output_tokens", 0)) for u in usage)}


TRANSCRIBE = """You transcribe a picture of a building sketch (a whiteboard drawing, a photo
of a scribble, a diagram) into plain text lines, one fact per line, using only these forms:
  A -> B -> C                      the first feeds the next (equipment to equipment or place);
                                   between two places (zone -> room) it means contains
  X, Y in P                        X and Y are part of place P (floors, zones, rooms)
  P on E: 16..26 degC, priority 9, BACnet analog-value,11, history ts-p
                                   point P (a set point, sensor, status) on equipment E with
                                   the attributes written next to it in the picture
  Schedule S for E: Mon-Fri 07:00-19:00, Sat 08:00-13:00, except 2026-12-25
  Policy N for Z: hours 06:00-20:00, setpoints 18..24
  B timezone Europe/Berlin
Write names exactly as drawn. Write only what the picture shows: never add a limit, unit,
reference, schedule or policy that is not drawn, and keep remarks such as "no limits" as a
line starting with #. Return only the lines, with no explanation."""


def build_request(skill: str, settings: dict[str, list[str]], machine: dict) -> tuple[str, dict]:
    """The user message and the id -> setting name map. `machine` holds this machine's extra
    facts: `asks_first`, `mcp_servers`, `credentials_set` (names only)."""
    ids = {f"s{i}": name for i, name in enumerate(settings, 1)}
    runtimes = []
    for sid, name in ids.items():
        entry = {"id": sid, "runtime": DESCRIBE.get(name, "a runtime"),
                 "tools": sorted(settings[name])}
        if name == "this machine":
            entry.update({"tools_that_ask_first": sorted(machine.get("asks_first", [])),
                          "mcp_servers_tools_not_listed": sorted(machine.get("mcp_servers", [])),
                          "credential_names_set": sorted(machine.get("credentials_set", []))})
        runtimes.append(entry)
    return json.dumps({"skill": skill, "runtimes": runtimes}, indent=1), ids


def _rows(reply: dict, ids: dict[str, str]) -> list[dict]:
    answers = reply.get("settings") if isinstance(reply.get("settings"), dict) else {}
    rows = []
    for sid, name in ids.items():
        a = answers.get(sid) if isinstance(answers.get(sid), dict) else {}
        verdict = str(a.get("verdict", "")).upper()
        rows.append({"setting": name,
                     "verdict": verdict if verdict in VERDICTS else "UNKNOWN",
                     "missing": [str(m) for m in a.get("missing") or [] if str(m).strip()],
                     "reason": str(a.get("reason") or ("no answer for this setting"
                                                       if not a else ""))[:300]})
    return rows


def llm_check(skill: str, settings: dict[str, list[str]], machine: dict, *, arm: str,
              provider: str, model: str | None, timeout: int = 120,
              complete=None) -> dict:
    """One check by the plain or the guided LLM. A failed call answers UNKNOWN everywhere."""
    if arm not in ARMS:
        raise ValueError(f"unknown arm {arm!r}")
    complete = complete or providers.complete
    system = SYSTEM + ("\n\n" + GUIDE if arm == "guided" else "")
    user, ids = build_request(skill, settings, machine)
    started = time.perf_counter()
    error = None
    with providers.metered() as usage:
        try:
            reply = providers.extract_json_object(
                complete(provider, system, user, model, timeout))
        except Exception as exc:  # noqa: BLE001 - any failure is shown, never a verdict
            reply, error = {}, f"{type(exc).__name__}: {str(exc)[:300]}"
    rows = _rows(reply, ids)
    if error:
        rows = [{**r, "reason": "the model call failed"} for r in rows]
    return {"arm": arm, "rows": rows, "error": error,
            "ms": round((time.perf_counter() - started) * 1000),
            "input_tokens": sum(int(u.get("input_tokens", 0))
                                + int(u.get("cache_read_input_tokens", 0)) for u in usage),
            "output_tokens": sum(int(u.get("output_tokens", 0)) for u in usage)}
