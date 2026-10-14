"""Fill the "write your own case" editor from this machine, read only.

    machine_context(root)        runtime + "What the agent could see" for a Claude Code agent here:
                                 the CLAUDE.md files, the memory index, git state, and a
                                 skillc.env.claude probe (tools, rules, MCP servers, credential names)
    list_turns(root)             the prompts of the recent Claude Code sessions in this repository
    session_turn(root, id, n)    one prompt as task + session lines (assistant / tool / out)
    upload_turns(text)           the same two for an uploaded transcript (.jsonl text), parsed in
    upload_turn(text, n)         memory and not stored; used by the hosted app

Nothing is written, sent or executed. Credential values are never read; only whether a variable is
set. Transcripts hide the model's thinking, so the agent's visible text stands in for its reasoning.
"""
from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

CLAUDE_HOME = Path.home() / ".claude"
MAX_ARTIFACT = 4000          # characters per artifact
MAX_ARTIFACTS = 19000        # the editor accepts 20,000
MAX_LINE = 1200              # characters per assistant / out line
MAX_SESSION = 19 * 1024      # the editor accepts 20 KB
MAX_STEPS = 60
SESSION_ID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
REMINDER = re.compile(r"<system-reminder>.*?</system-reminder>", re.S)


def project_dir(root: Path) -> Path:
    """Where Claude Code keeps this repository's transcripts and memory."""
    return CLAUDE_HOME / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(root.resolve()))


def _clip(text: str, n: int) -> str:
    text = text.strip()
    return text if len(text) <= n else text[:n].rstrip() + f"\n... ({len(text) - n} more characters)"


def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _git(root: Path, *args: str) -> str:
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True,
                           timeout=10, encoding="utf-8", errors="replace")
        return r.stdout.strip() if r.returncode == 0 else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def _git_summary(root: Path) -> str:
    branch = _git(root, "branch", "--show-current")
    remotes = sorted({" ".join(l.split()[:2]) for l in _git(root, "remote", "-v").splitlines() if l})
    status = [l for l in _git(root, "status", "--porcelain").splitlines() if l]
    log = _git(root, "log", "--oneline", "-5")
    lines = [f"branch: {branch or '(detached or not a repository)'}"]
    lines += [f"remote: {r}" for r in remotes]
    lines.append(f"uncommitted changes: {len(status)} path(s)")
    if log:
        lines += ["recent commits:", *("  " + l for l in log.splitlines())]
    return "\n".join(lines)


def _probe_summary(root: Path) -> str:
    """The skillc.env.claude probe, as text. No egress check: nothing leaves the machine."""
    from skillc.env import claude
    env = claude.probe(root=root, check_egress=False)
    attrs = lambda n: n.get("attrs", {})
    tools = sorted(n["name"] for n in env.of_kind("tool"))
    lines = ["built-in tools: " + ", ".join(tools)]
    for kind, label in (("role", "allow / ask rules"), ("deny", "deny rules")):
        for n in env.of_kind(kind):
            acts = attrs(n).get("actions") or []
            if acts:
                lines.append(f"{label} ({n['name']}): " + ", ".join(map(str, acts)))
    servers = env.of_kind("mcp_server")
    ready = sorted(n["name"] for n in servers if not attrs(n).get("needs_auth"))
    pending = sorted(n["name"] for n in servers if attrs(n).get("needs_auth"))
    lines.append("MCP servers connected: " + (", ".join(ready) or "none"))
    if pending:
        lines.append(f"MCP servers configured but not signed in: {len(pending)}")
    creds = [n for n in env.of_kind("service") if attrs(n).get("type") == "credential"]
    lines.append("credentials set (names only): "
                 + (", ".join(sorted(n["name"] for n in creds if attrs(n).get("available"))) or "none"))
    plats = [n["name"] for n in env.of_kind("service")
             if attrs(n).get("type") == "platform" and attrs(n).get("available")]
    lines.append("platform: " + (", ".join(plats) or "unknown"))
    for n in env.of_kind("scope"):
        if attrs(n).get("writable"):
            lines.append(f"writable: {n['name']}")
    return "\n".join(lines)


def machine_context(root: Path) -> dict:
    """{runtime, artifacts, sources}: what a Claude Code agent started in `root` loads."""
    root = root.resolve()
    arts, sources = [], []

    def add(name: str, text: str | None, source: str) -> None:
        if text and text.strip():
            arts.append(f"=== {name} ===\n{_clip(text, MAX_ARTIFACT)}")
            sources.append(source)

    add("~/.claude/CLAUDE.md (user instructions)", _read(CLAUDE_HOME / "CLAUDE.md"), "~/.claude/CLAUDE.md")
    for name in ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md"):
        add(f"{name} (project instructions)", _read(root / name), name)
    add("memory index (MEMORY.md)", _read(project_dir(root) / "memory" / "MEMORY.md"), "memory/MEMORY.md")
    add("git", _git_summary(root), "git")
    try:
        add("environment (skillc.env.claude probe)", _probe_summary(root), "skillc.env.claude.probe")
    except Exception as e:  # the probe is best effort; the rest still fills the editor
        add("environment (skillc.env.claude probe)", f"probe failed: {e}", "skillc.env.claude.probe")
    text = "\n".join(arts)
    if len(text) > MAX_ARTIFACTS:
        text = text[:MAX_ARTIFACTS].rstrip() + "\n... (cut to fit the editor)"
    return {"runtime": "developer-sandbox", "artifacts": text, "sources": sources}


# --- Claude Code transcripts -------------------------------------------------------------------

def _prompt_text(rec: dict) -> str | None:
    """The text of a prompt the user typed, or None for tool results, meta and command records."""
    if rec.get("type") != "user" or rec.get("isMeta") or rec.get("isSidechain"):
        return None
    content = (rec.get("message") or {}).get("content")
    if isinstance(content, list):
        if any(b.get("type") == "tool_result" for b in content if isinstance(b, dict)):
            return None
        content = "\n".join(b.get("text", "") for b in content
                            if isinstance(b, dict) and b.get("type") == "text")
    if not isinstance(content, str):
        return None
    text = REMINDER.sub("", content).strip()
    if not text or text.startswith(("<", "[Request interrupted", "Caveat:")):
        return None
    return text


def _parse_lines(lines):
    for line in lines:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            yield rec


def _records(path: Path):
    with path.open(encoding="utf-8", errors="replace") as f:
        yield from _parse_lines(f)


def _turns(records) -> tuple[list[dict], str]:
    """(prompts typed by the user, the session's title) for one transcript."""
    turns, title = [], ""
    for rec in records:
        if rec.get("type") == "ai-title" and rec.get("aiTitle"):
            title = str(rec["aiTitle"])
        text = _prompt_text(rec)
        if text is not None:
            turns.append({"turn": len(turns), "when": str(rec.get("timestamp", "")),
                          "prompt": _clip(text.replace("\n", " "), 140)})
    return turns, title


def list_turns(root: Path, sessions: int = 8, per_session: int = 30) -> list[dict]:
    """Recent sessions, newest first, each with the prompts the user typed in it."""
    d = project_dir(root)
    files = sorted((p for p in d.glob("*.jsonl") if SESSION_ID.match(p.stem)),
                   key=lambda p: p.stat().st_mtime, reverse=True)[:sessions]
    out = []
    for p in files:
        turns, title = _turns(_records(p))
        if turns:
            when = datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            out.append({"id": p.stem, "modified": when, "title": title, "turns": turns[-per_session:]})
    return out


def _result_text(block: dict) -> str:
    c = block.get("content")
    if isinstance(c, list):
        c = "\n".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
    return REMINDER.sub("", c if isinstance(c, str) else "").strip()


def _one_line(text: str) -> str:
    return text.replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n")


def session_turn(root: Path, session_id: str, turn: int) -> dict:
    """One prompt of a transcript of this repository; see _turn."""
    if not SESSION_ID.match(session_id or ""):
        raise ValueError("unknown session")
    path = project_dir(root) / f"{session_id}.jsonl"
    if not path.is_file():
        raise ValueError("unknown session")
    return _turn(_records(path), turn)


def upload_turns(text: str) -> dict:
    """{title, turns} of an uploaded transcript."""
    turns, title = _turns(_parse_lines(text.splitlines()))
    if not turns:
        raise ValueError("no prompts found: upload a Claude Code transcript (.jsonl) from "
                         "~/.claude/projects/<project>/")
    return {"title": title, "turns": turns}


def upload_turn(text: str, turn: int) -> dict:
    return _turn(_parse_lines(text.splitlines()), turn)


def _turn(records, turn: int) -> dict:
    """{task, session, steps, truncated}: prompt `turn` and what the agent did next, up to the
    next prompt the user typed. Subagent (sidechain) records are left out."""
    task, n, lines, steps, size, dropped = None, -1, [], 0, 0, 0
    for rec in records:
        text = _prompt_text(rec)
        if text is not None:
            n += 1
            if n == turn:
                task = text
                continue
            if n > turn:
                break
        if n != turn or rec.get("isSidechain"):
            continue
        content = (rec.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if rec.get("type") == "assistant" and b.get("type") == "text" and b.get("text", "").strip():
                line = "assistant: " + _one_line(_clip(b["text"], MAX_LINE))
            elif rec.get("type") == "assistant" and b.get("type") == "tool_use":
                name = re.sub(r"[^A-Za-z0-9_.:-]", "_", b.get("name") or "tool")
                inp = b.get("input") if isinstance(b.get("input"), dict) else {}
                line = f"tool: {name} " + json.dumps(inp, ensure_ascii=False)
                if len(line) > MAX_LINE * 2:
                    short = {k: (_clip(v, 300) if isinstance(v, str) else v) for k, v in inp.items()}
                    line = f"tool: {name} " + json.dumps(short, ensure_ascii=False)
            elif rec.get("type") == "user" and b.get("type") == "tool_result":
                if not lines or not lines[-1].startswith("tool:"):
                    continue                     # `out:` must follow its tool line
                line = "out: " + _one_line(_clip(_result_text(b) or "(empty)", MAX_LINE))
            else:
                continue
            cost = len(line.encode("utf-8")) + 1
            if steps >= MAX_STEPS or size + cost > MAX_SESSION:
                dropped += 1
                continue
            lines.append(line)
            steps, size = steps + 1, size + cost
    if task is None:
        raise ValueError("unknown turn")
    if dropped:
        lines.append(f"# cut to fit the editor: {dropped} more step(s) not imported")
    if not steps:
        lines = ["# the agent took no recorded steps after this prompt"]
    return {"task": _clip(task, 3900), "session": "\n".join(lines) + "\n", "steps": steps,
            "truncated": dropped}
